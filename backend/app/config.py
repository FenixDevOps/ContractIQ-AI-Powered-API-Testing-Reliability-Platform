"""Environment-driven settings for the ContractIQ API."""

import os


def _parse_origins(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]


APP_NAME = os.getenv("CONTRACTIQ_APP_NAME", "ContractIQ API")
APP_VERSION = os.getenv("CONTRACTIQ_APP_VERSION", "0.1.0")
ALLOWED_ORIGINS = _parse_origins(
    os.getenv(
        "CONTRACTIQ_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
)