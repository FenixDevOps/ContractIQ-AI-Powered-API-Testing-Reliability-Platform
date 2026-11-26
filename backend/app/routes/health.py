"""Health and application metadata endpoints."""

from fastapi import APIRouter
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import APP_NAME, APP_VERSION
from app.database.connection import engine

router = APIRouter(tags=["system"])


@router.get("/health", summary="Check backend health")
async def health_check() -> dict[str, str]:
    """Return a simple health signal for local frontend connectivity checks."""
    return {"status": "healthy"}


@router.get("/ready", summary="Check application readiness")
async def readiness_check() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The database is not ready.",
        ) from exc
    return {"status": "ready", "database": "connected"}


@router.get("/api/v1/status", summary="Get application status")
async def application_status() -> dict[str, str]:
    return {"application": APP_NAME, "status": "operational", "version": APP_VERSION}