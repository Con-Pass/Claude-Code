"""
Metadata CRUD execution API endpoints.

These endpoints execute approved metadata CRUD actions after user approval.
They require authentication and perform the actual operations against ConPass API.
"""

from fastapi import APIRouter
from app.api.v1.metadata_crud.update_metadata import router as update_router
from app.api.v1.metadata_crud.create_metadata_key import router as create_key_router
from app.api.v1.metadata_crud.delete_metadata_key import router as delete_key_router
from app.api.v1.metadata_crud.update_metadata_key import router as update_key_router
from app.api.v1.metadata_crud.update_directory_visibility import router as update_directory_visibility_router
from app.api.v1.metadata_crud.review_queue import router as review_queue_router

# Combine all routers into a single router
metadata_crud_router = APIRouter()
metadata_crud_router.include_router(update_router)
metadata_crud_router.include_router(create_key_router)
metadata_crud_router.include_router(delete_key_router)
metadata_crud_router.include_router(update_key_router)
metadata_crud_router.include_router(update_directory_visibility_router)
metadata_crud_router.include_router(review_queue_router)

__all__ = ["metadata_crud_router"]
