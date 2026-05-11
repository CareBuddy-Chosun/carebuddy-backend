from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    guardians,
    hospitals,
    notifications,
    sessions,
    users,
    voice,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(guardians.router)
api_router.include_router(sessions.router)
api_router.include_router(hospitals.router)
api_router.include_router(voice.router)
api_router.include_router(notifications.router)
