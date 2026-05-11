import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.guardian import Guardian
from app.schemas.auth import GuardianCreate

MAX_GUARDIANS = 2


async def create_guardian(
    db: AsyncSession, user_id: uuid.UUID, data: GuardianCreate
) -> Guardian:
    count_result = await db.execute(
        select(func.count()).where(Guardian.user_id == user_id)
    )
    if count_result.scalar() >= MAX_GUARDIANS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_GUARDIANS} guardians allowed",
        )

    guardian = Guardian(
        user_id=user_id,
        name=data.name,
        phone=data.phone,
        relationship_label=data.relationship,
    )
    db.add(guardian)
    await db.commit()
    await db.refresh(guardian)
    return guardian


async def update_guardian(
    db: AsyncSession,
    user_id: uuid.UUID,
    guardian_id: uuid.UUID,
    data: GuardianCreate,
) -> Guardian:
    guardian = await _get_guardian_or_404(db, user_id, guardian_id)
    guardian.name = data.name
    guardian.phone = data.phone
    guardian.relationship_label = data.relationship
    await db.commit()
    await db.refresh(guardian)
    return guardian


async def delete_guardian(
    db: AsyncSession, user_id: uuid.UUID, guardian_id: uuid.UUID
) -> None:
    guardian = await _get_guardian_or_404(db, user_id, guardian_id)
    await db.delete(guardian)
    await db.commit()


async def _get_guardian_or_404(
    db: AsyncSession, user_id: uuid.UUID, guardian_id: uuid.UUID
) -> Guardian:
    result = await db.execute(
        select(Guardian).where(
            Guardian.id == guardian_id, Guardian.user_id == user_id
        )
    )
    guardian = result.scalar_one_or_none()
    if not guardian:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Guardian not found"
        )
    return guardian
