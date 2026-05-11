from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.auth_service import authenticate_user, create_user, get_user_by_email
from app.services.blocklist_service import add_to_blocklist
from app.services.token_service import (
    create_refresh_token_record,
    revoke_refresh_token,
    validate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if await get_user_by_email(db, data.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    user = await create_user(db, data)

    access_token = create_access_token(user.email)
    refresh_token = create_refresh_token(user.email)
    await create_refresh_token_record(db, user.id, refresh_token)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, data.email, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    access_token = create_access_token(user.email)
    refresh_token = create_refresh_token(user.email)
    await create_refresh_token_record(db, user.id, refresh_token)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
            )
        email: str = payload["sub"]
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    # Validate against DB record
    token_record = await validate_refresh_token(db, data.refresh_token)
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked or expired"
        )

    user = await get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    # Rotate: revoke old, issue new
    await revoke_refresh_token(db, data.refresh_token)

    new_access = create_access_token(user.email)
    new_refresh = create_refresh_token(user.email)
    await create_refresh_token_record(db, user.id, new_refresh)
    await db.commit()

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        user_id=user.id,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    data: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    # Revoke refresh token in DB
    await revoke_refresh_token(db, data.refresh_token)
    await db.commit()

    # Blocklist the access token JTI if provided via header
    # The access token will expire naturally, but blocklisting provides immediate invalidation
    try:
        payload = decode_token(data.refresh_token)
        jti = payload.get("jti")
        if jti:
            ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            await add_to_blocklist(redis, jti, ttl)
    except JWTError:
        pass  # Token already invalid, nothing to blocklist
