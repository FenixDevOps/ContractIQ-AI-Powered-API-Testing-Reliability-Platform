"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS, APP_NAME, APP_VERSION
from app.routes.health import router as health_router
from app.routes.projects import router as projects_router
from app.routes.specifications import router as specifications_router
from app.routes.endpoints import router as endpoints_router
from app.routes.testing import router as testing_router

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="OpenAPI contract import and automated API testing for ContractIQ.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/", summary="Get project information")
async def root() -> dict[str, str]:
    return {
        "project": "ContractIQ",
        "description": "AI-powered API testing and reliability platform",
        "stage": "Stage 3: Automated API Testing",
        "docs": "/docs",
    }


app.include_router(health_router)
app.include_router(projects_router)
app.include_router(specifications_router)
app.include_router(endpoints_router)
app.include_router(testing_router)
