import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.guardian import Guardian
from app.models.session import Session
from app.models.user import User
from app.schemas.user import (
    GuardianCreateRequest,
    GuardianResponse,
    GuardianUpdateRequest,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter(prefix="/users", tags=["users"])


def _guardian_to_response(guardian: Guardian) -> GuardianResponse:
    return GuardianResponse(
        id=guardian.id,
        name=guardian.name,
        phone=guardian.phone,
        relationship=guardian.relationship_label,
    )


async def _build_user_response(db: AsyncSession, user: User) -> UserResponse:
    guardians_result = await db.execute(
        select(Guardian)
        .where(Guardian.user_id == user.id)
        .order_by(Guardian.created_at)
    )
    guardians = guardians_result.scalars().all()

    count_result = await db.execute(
        select(func.count()).select_from(Session).where(Session.user_id == user.id)
    )
    session_count = count_result.scalar_one()

    return UserResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        date_of_birth=user.date_of_birth,
        consent_data_storage=user.consent_data_storage,
        guardians=[_guardian_to_response(g) for g in guardians],
        created_at=user.created_at,
        session_count=session_count,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _build_user_response(db, current_user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.consent_data_storage is not None:
        current_user.consent_data_storage = data.consent_data_storage
        if data.consent_data_storage and current_user.consent_granted_at is None:
            current_user.consent_granted_at = datetime.now(timezone.utc)
        elif not data.consent_data_storage:
            current_user.consent_granted_at = None
    await db.commit()
    await db.refresh(current_user)
    return await _build_user_response(db, current_user)


@router.post(
    "/me/guardians",
    response_model=GuardianResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_guardian(
    data: GuardianCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    guardian = Guardian(
        user_id=current_user.id,
        name=data.name,
        phone=data.phone,
        relationship_label=data.relationship,
    )
    db.add(guardian)
    await db.commit()
    await db.refresh(guardian)
    return _guardian_to_response(guardian)


@router.patch("/me/guardians/{guardian_id}", response_model=GuardianResponse)
async def update_guardian(
    guardian_id: uuid.UUID,
    data: GuardianUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    guardian = await _get_owned_guardian(db, guardian_id, current_user)
    guardian.name = data.name
    guardian.phone = data.phone
    guardian.relationship_label = data.relationship
    await db.commit()
    await db.refresh(guardian)
    return _guardian_to_response(guardian)


@router.delete("/me/guardians/{guardian_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_guardian(
    guardian_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    guardian = await _get_owned_guardian(db, guardian_id, current_user)
    await db.delete(guardian)
    await db.commit()


async def _get_owned_guardian(
    db: AsyncSession, guardian_id: uuid.UUID, current_user: User
) -> Guardian:
    result = await db.execute(select(Guardian).where(Guardian.id == guardian_id))
    guardian = result.scalar_one_or_none()
    if not guardian:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Guardian not found"
        )
    if guardian.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your guardian"
        )
    return guardian
