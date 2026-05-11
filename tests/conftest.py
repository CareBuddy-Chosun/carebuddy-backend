import asyncio
import os
import uuid as _uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, String, TypeDecorator, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.core.security import create_access_token
import app.models  # noqa: F401 — register all models
from app.main import app as fastapi_app

# In-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite://"

engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine.sync_engine, "connect")
def _enable_sqlite_fk(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class SQLiteUUID(TypeDecorator):
    """Store UUID as string in SQLite."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return _uuid.UUID(value)
        return value


def _patch_pg_types():
    """Replace PostgreSQL-specific column types with SQLite-compatible equivalents."""
    from sqlalchemy.dialects.postgresql import JSONB, UUID

    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, UUID):
                column.type = SQLiteUUID()
            elif isinstance(column.type, JSONB):
                column.type = JSON()
            elif hasattr(column.type, "enums"):
                column.type = String(50)


_patch_pg_types()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


class FakeRedis:
    """Minimal in-memory Redis stub for tests."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def incr(self, key: str) -> int:
        val = int(self._store.get(key, "0")) + 1
        self._store[key] = str(val)
        return val

    async def expire(self, key: str, seconds: int) -> None:
        pass

    async def ttl(self, key: str) -> int:
        return 60


_fake_redis = FakeRedis()


async def _override_get_redis():
    return _fake_redis


fastapi_app.dependency_overrides[get_db] = _override_get_db
fastapi_app.dependency_overrides[get_redis] = _override_get_redis


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def authenticated_client(async_client: AsyncClient) -> AsyncClient:
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "TestPass1",
            "full_name": "Test User",
        },
    )
    token = create_access_token("test@example.com")
    async_client.headers["Authorization"] = f"Bearer {token}"
    return async_client


@pytest.fixture
async def second_authenticated_client(async_client: AsyncClient) -> AsyncClient:
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "other@example.com",
            "password": "OtherPass1",
            "full_name": "Other User",
        },
    )
    token = create_access_token("other@example.com")
    async_client.headers["Authorization"] = f"Bearer {token}"
    return async_client
