from fastapi import APIRouter
from handlers import root_router


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(root_router)
