from fastapi import APIRouter

from app.api.v1.endpoints import auth, hospitals, sessions, voice

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(sessions.router)
api_router.include_router(hospitals.router)
api_router.include_router(voice.router)
