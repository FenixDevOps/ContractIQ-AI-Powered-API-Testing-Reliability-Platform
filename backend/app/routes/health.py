"""Health and application metadata endpoints."""

from fastapi import APIRouter

from app.config import APP_NAME, APP_VERSION

router = APIRouter(tags=["system"])


@router.get("/health", summary="Check backend health")
async def health_check() -> dict[str, str]:
    """Return a simple health signal for local frontend connectivity checks."""
    return {"status": "healthy"}


@router.get("/api/v1/status", summary="Get application status")
async def application_status() -> dict[str, str]:
    return {"application": APP_NAME, "status": "operational", "version": APP_VERSION}