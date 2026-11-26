"""Environment-driven settings for the ContractIQ API."""

import os


def _parse_origins(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]

def _parse_hosts(value: str) -> set[str]:
    return {host.strip().lower().rstrip(".") for host in value.split(",") if host.strip()}


def _parse_project_ids(value: str) -> set[str]:
    return {project_id.strip() for project_id in value.split(",") if project_id.strip()}


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
MONITORING_AUTH_TOKEN = os.getenv("CONTRACTIQ_MONITORING_AUTH_TOKEN", "")
MONITORING_ALLOWED_PROJECT_IDS = _parse_project_ids(
    os.getenv("CONTRACTIQ_MONITORING_ALLOWED_PROJECT_IDS", "")
)
MONITORING_SCHEDULER_ENABLED = os.getenv("CONTRACTIQ_MONITORING_SCHEDULER_ENABLED", "true").lower() == "true"
MONITORING_MIN_INTERVAL_SECONDS = 30
MONITORING_MAX_INTERVAL_SECONDS = 3600
MONITORING_MAX_ENDPOINTS = 20
MONITORING_MAX_TIMEOUT_SECONDS = 30
MONITORING_MAX_RESPONSE_BYTES = int(os.getenv("CONTRACTIQ_MONITORING_MAX_RESPONSE_BYTES", str(256 * 1024)))
MONITORING_SCHEDULER_POLL_SECONDS = 2
MONITORING_LEASE_SECONDS = 60
MONITORING_ALERT_COOLDOWN_SECONDS = 900
ANOMALY_MIN_TRAINING_SAMPLES = int(os.getenv("CONTRACTIQ_ANOMALY_MIN_TRAINING_SAMPLES", "100"))
ANOMALY_RETRAIN_NEW_SAMPLES = int(os.getenv("CONTRACTIQ_ANOMALY_RETRAIN_NEW_SAMPLES", "50"))
ANOMALY_CONTAMINATION = float(os.getenv("CONTRACTIQ_ANOMALY_CONTAMINATION", "0.05"))

if MONITORING_AUTH_TOKEN and len(MONITORING_AUTH_TOKEN) < 32:
    raise ValueError("CONTRACTIQ_MONITORING_AUTH_TOKEN must contain at least 32 characters")
if not 0 < ANOMALY_CONTAMINATION <= 0.5:
    raise ValueError("CONTRACTIQ_ANOMALY_CONTAMINATION must be greater than 0 and at most 0.5")
if ANOMALY_MIN_TRAINING_SAMPLES < 20:
    raise ValueError("CONTRACTIQ_ANOMALY_MIN_TRAINING_SAMPLES must be at least 20")
if ANOMALY_RETRAIN_NEW_SAMPLES < 1:
    raise ValueError("CONTRACTIQ_ANOMALY_RETRAIN_NEW_SAMPLES must be positive")
if MONITORING_MAX_RESPONSE_BYTES < 1:
    raise ValueError("CONTRACTIQ_MONITORING_MAX_RESPONSE_BYTES must be positive")