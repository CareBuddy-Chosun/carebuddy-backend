from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import verify_password
from app.models.session import Session
from app.models.user import User
from app.schemas.auth import DeleteAccountRequest, UserProfileResponse, UserProfileUpdate
from app.services.token_service import revoke_all_user_tokens


async def get_user_profile(db: AsyncSession, user: User) -> UserProfileResponse:
    # Reload with guardians
    result = await db.execute(
        select(User).where(User.id == user.id).options(selectinload(User.guardians))
    )
    user = result.scalar_one()

    session_count_result = await db.execute(
        select(func.count()).where(Session.user_id == user.id)
    )
    session_count = session_count_result.scalar()

    return UserProfileResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        date_of_birth=user.date_of_birth,
        consent_data_storage=user.consent_data_storage,
        guardians=[
            {
                "id": g.id,
                "name": g.name,
                "phone": g.phone,
                "relationship": g.relationship_label,
            }
            for g in user.guardians
        ],
        created_at=user.created_at,
        session_count=session_count,
    )


async def update_user_profile(
    db: AsyncSession, user: User, data: UserProfileUpdate
) -> User:
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.consent_data_storage is not None:
        if data.consent_data_storage and not user.consent_data_storage:
            user.consent_granted_at = datetime.now(timezone.utc)
        user.consent_data_storage = data.consent_data_storage
    await db.commit()
    await db.refresh(user)
    return user


async def delete_user_account(
    db: AsyncSession, user: User, data: DeleteAccountRequest
) -> None:
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Incorrect password",
        )
    await revoke_all_user_tokens(db, user.id)
    await db.delete(user)
    await db.commit()
