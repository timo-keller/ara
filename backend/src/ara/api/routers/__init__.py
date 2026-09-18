"""Mounted REST routers."""

from fastapi import APIRouter

api_router = APIRouter(prefix="/api")
auth_router = APIRouter(prefix="/auth")
