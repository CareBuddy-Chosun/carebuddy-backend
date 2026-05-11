import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.audit_log import AuditLog
from app.services.audit_service import log_deletion


@pytest.mark.asyncio
class TestAuditLog:
    async def test_log_deletion_creates_record(self):
        """log_deletion should create an AuditLog entry."""
        from tests.conftest import TestSessionLocal

        async with TestSessionLocal() as db:
            user_id = uuid.uuid4()
            resource_id = uuid.uuid4()

            await log_deletion(
                db,
                user_id=user_id,
                resource_type="session",
                resource_id=resource_id,
                ip_address="127.0.0.1",
                metadata={"reason": "user_request"},
            )
            await db.commit()

            result = await db.execute(
                select(AuditLog).where(AuditLog.resource_type == "session")
            )
            entry = result.scalar_one_or_none()
            assert entry is not None
            assert entry.action == "delete"
            assert entry.resource_type == "session"
            assert entry.ip_address == "127.0.0.1"
