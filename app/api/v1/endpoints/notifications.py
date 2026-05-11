import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.session import Session
from app.models.user import User
from app.services.notification_service import send_guardian_sms

router = APIRouter(prefix="/sessions", tags=["notifications"])


@router.post("/{session_id}/notify-guardians")
async def notify_guardians(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify session belongs to user and is EMERGENCY
    result = await db.execute(
        select(Session).where(
            Session.id == session_id, Session.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    if session.triage_level != "EMERGENCY":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Guardian notification only available for EMERGENCY triage",
        )

    # Load guardians
    user_result = await db.execute(
        select(User).where(User.id == current_user.id).options(selectinload(User.guardians))
    )
    user = user_result.scalar_one()
    if not user.guardians:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No guardians configured",
        )

    notifications = []
    for guardian in user.guardians:
        success = await send_guardian_sms(guardian.phone, user.full_name)
        notifications.append({
            "guardian_name": guardian.name,
            "phone": guardian.phone,
            "status": "sent" if success else "failed",
        })

    return {"notifications": notifications}
