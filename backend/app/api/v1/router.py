from fastapi import APIRouter

from app.api.v1.endpoints import admin, conversation, health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(conversation.router, tags=["conversation"])
api_router.include_router(admin.router, tags=["admin"])
