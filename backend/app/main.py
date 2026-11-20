"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS, APP_NAME, APP_VERSION
from app.routes.health import router as health_router

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Stage 1 foundation for the ContractIQ API reliability platform.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/", summary="Get project information")
async def root() -> dict[str, str]:
    return {
        "project": "ContractIQ",
        "description": "AI-powered API testing and reliability platform",
        "stage": "Stage 1: Foundation",
        "docs": "/docs",
    }


app.include_router(health_router)