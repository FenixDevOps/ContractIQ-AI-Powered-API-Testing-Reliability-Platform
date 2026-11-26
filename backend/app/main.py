"""FastAPI application entry point."""

import asyncio
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect

from app.config import (
    ALLOWED_ORIGINS,
    APP_NAME,
    APP_VERSION,
    MONITORING_SCHEDULER_ENABLED,
)
from app.database.connection import engine
from app.routes.health import router as health_router
from app.routes.auth import router as auth_router
from app.routes.projects import router as projects_router
from app.routes.specifications import router as specifications_router
from app.routes.endpoints import router as endpoints_router
from app.routes.testing import router as testing_router
from app.routes.compatibility import router as compatibility_router
from app.routes.monitoring import router as monitoring_router
from app.services.monitoring_events import event_hub
from app.services.monitoring_runner import monitoring_scheduler

logger = logging.getLogger(__name__)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _monitoring_schema_available() -> bool:
    return inspect(engine).has_table("monitoring_configs")


@asynccontextmanager
async def lifespan(application: FastAPI):
    event_hub.set_loop(asyncio.get_running_loop())
    schema_available = await asyncio.to_thread(_monitoring_schema_available)
    if MONITORING_SCHEDULER_ENABLED and schema_available:
        await monitoring_scheduler.start()
    elif MONITORING_SCHEDULER_ENABLED:
        logger.warning("Monitoring scheduler is not started because the monitoring migration is not applied.")
    try:
        yield
    finally:
        await monitoring_scheduler.stop()

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="OpenAPI contract import, compatibility analysis, API testing, and real-time monitoring for ContractIQ.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def add_request_correlation(request: Request, call_next):
    supplied_id = request.headers.get("X-Request-ID", "")
    request_id = supplied_id if REQUEST_ID_PATTERN.fullmatch(supplied_id) else uuid.uuid4().hex
    request.state.request_id = request_id
    started_at = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "http_request_completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
        },
    )
    return response


@app.get("/", summary="Get project information")
async def root() -> dict[str, str]:
    return {
        "project": "ContractIQ",
        "description": "AI-powered API testing and reliability platform",
        "stage": "Stage 6: Production Quality",
        "docs": "/docs",
    }


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(specifications_router)
app.include_router(endpoints_router)
app.include_router(testing_router)
app.include_router(compatibility_router)
app.include_router(monitoring_router)
