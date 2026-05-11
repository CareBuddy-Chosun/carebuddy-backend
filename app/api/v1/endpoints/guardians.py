import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import GuardianCreate, GuardianSchema
from app.services.guardian_service import create_guardian, delete_guardian, update_guardian

router = APIRouter(prefix="/users/me/guardians", tags=["guardians"])


@router.post("", response_model=GuardianSchema, status_code=status.HTTP_201_CREATED)
async def add_guardian(
    data: GuardianCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    guardian = await create_guardian(db, current_user.id, data)
    return GuardianSchema(
        id=guardian.id,
        name=guardian.name,
        phone=guardian.phone,
        relationship=guardian.relationship_label,
    )


@router.patch("/{guardian_id}", response_model=GuardianSchema)
async def edit_guardian(
    guardian_id: uuid.UUID,
    data: GuardianCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    guardian = await update_guardian(db, current_user.id, guardian_id, data)
    return GuardianSchema(
        id=guardian.id,
        name=guardian.name,
        phone=guardian.phone,
        relationship=guardian.relationship_label,
    )


@router.delete("/{guardian_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_guardian(
    guardian_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await delete_guardian(db, current_user.id, guardian_id)
