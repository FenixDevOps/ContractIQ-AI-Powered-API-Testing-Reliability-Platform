"""Environment-driven settings for the ContractIQ API."""

import os


def _parse_origins(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]

def _parse_hosts(value: str) -> set[str]:
    return {host.strip().lower().rstrip(".") for host in value.split(",") if host.strip()}


APP_NAME = os.getenv("CONTRACTIQ_APP_NAME", "ContractIQ API")
APP_VERSION = os.getenv("CONTRACTIQ_APP_VERSION", "0.1.0")
ALLOWED_ORIGINS = _parse_origins(
    os.getenv(
        "CONTRACTIQ_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
)
DATABASE_URL = os.getenv(
    "CONTRACTIQ_DATABASE_URL",
    "sqlite:///./contractiq.db",
)
MAX_UPLOAD_SIZE = int(os.getenv("CONTRACTIQ_MAX_UPLOAD_SIZE", str(5 * 1024 * 1024)))
TEST_ALLOWED_TARGET_HOSTS = _parse_hosts(os.getenv("CONTRACTIQ_TEST_ALLOWED_TARGET_HOSTS", ""))
TEST_ALLOWED_TARGET_PORTS = {
    int(port.strip()) for port in os.getenv("CONTRACTIQ_TEST_ALLOWED_TARGET_PORTS", "80,443").split(",")
    if port.strip().isdigit()
}
TEST_ALLOW_PRIVATE_TARGETS = os.getenv("CONTRACTIQ_TEST_ALLOW_PRIVATE_TARGETS", "false").lower() == "true"
TEST_MAX_RESPONSE_BYTES = int(os.getenv("CONTRACTIQ_TEST_MAX_RESPONSE_BYTES", str(1024 * 1024)))
TEST_MAX_CASES_PER_RUN = int(os.getenv("CONTRACTIQ_TEST_MAX_CASES_PER_RUN", "100"))