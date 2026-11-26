"""Environment-driven settings for the ContractIQ API."""

import os
import secrets


def _parse_origins(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]

def _parse_hosts(value: str) -> set[str]:
    return {host.strip().lower().rstrip(".") for host in value.split(",") if host.strip()}


APP_NAME = os.getenv("CONTRACTIQ_APP_NAME", "ContractIQ API")
APP_VERSION = os.getenv("CONTRACTIQ_APP_VERSION", "0.1.0")
ENVIRONMENT = os.getenv("CONTRACTIQ_ENVIRONMENT", "development").strip().lower()
SECRET_KEY = os.getenv("CONTRACTIQ_SECRET_KEY") or os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if ENVIRONMENT in {"production", "prod"}:
        raise ValueError("CONTRACTIQ_SECRET_KEY is required in production")
    SECRET_KEY = secrets.token_urlsafe(48)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("CONTRACTIQ_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("CONTRACTIQ_REFRESH_TOKEN_EXPIRE_DAYS", "30"))
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("CONTRACTIQ_PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "30"))
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS = int(os.getenv("CONTRACTIQ_EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS", "24"))
AUTH_COOKIE_SECURE = os.getenv(
    "CONTRACTIQ_AUTH_COOKIE_SECURE",
    str(ENVIRONMENT in {"production", "prod"}).lower(),
).lower() == "true"
AUTH_COOKIE_SAMESITE = os.getenv("CONTRACTIQ_AUTH_COOKIE_SAMESITE", "lax").lower()
DEFAULT_AUTH_ALLOW_REGISTRATION = "false" if ENVIRONMENT in {"production", "prod"} else "true"
AUTH_ALLOW_REGISTRATION = os.getenv(
    "CONTRACTIQ_AUTH_ALLOW_REGISTRATION",
    DEFAULT_AUTH_ALLOW_REGISTRATION,
).lower() == "true"
AUTH_REQUIRE_EMAIL_VERIFICATION = os.getenv(
    "CONTRACTIQ_AUTH_REQUIRE_EMAIL_VERIFICATION",
    str(ENVIRONMENT in {"production", "prod"}).lower(),
).lower() == "true"
FRONTEND_BASE_URL = os.getenv("CONTRACTIQ_FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
SMTP_HOST = os.getenv("CONTRACTIQ_SMTP_HOST", "")
SMTP_PORT = int(os.getenv("CONTRACTIQ_SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("CONTRACTIQ_SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("CONTRACTIQ_SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("CONTRACTIQ_SMTP_FROM_EMAIL", "")
SMTP_USE_TLS = os.getenv("CONTRACTIQ_SMTP_USE_TLS", "true").lower() == "true"
SMTP_TIMEOUT_SECONDS = float(os.getenv("CONTRACTIQ_SMTP_TIMEOUT_SECONDS", "10"))
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

if not 0 < ANOMALY_CONTAMINATION <= 0.5:
    raise ValueError("CONTRACTIQ_ANOMALY_CONTAMINATION must be greater than 0 and at most 0.5")
if ANOMALY_MIN_TRAINING_SAMPLES < 20:
    raise ValueError("CONTRACTIQ_ANOMALY_MIN_TRAINING_SAMPLES must be at least 20")
if ANOMALY_RETRAIN_NEW_SAMPLES < 1:
    raise ValueError("CONTRACTIQ_ANOMALY_RETRAIN_NEW_SAMPLES must be positive")
if MONITORING_MAX_RESPONSE_BYTES < 1:
    raise ValueError("CONTRACTIQ_MONITORING_MAX_RESPONSE_BYTES must be positive")
if ACCESS_TOKEN_EXPIRE_MINUTES < 1 or REFRESH_TOKEN_EXPIRE_DAYS < 1:
    raise ValueError("Authentication token lifetimes must be positive")
if PASSWORD_RESET_TOKEN_EXPIRE_MINUTES < 5:
    raise ValueError("CONTRACTIQ_PASSWORD_RESET_TOKEN_EXPIRE_MINUTES must be at least 5")
if EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS < 1:
    raise ValueError("CONTRACTIQ_EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS must be positive")
if AUTH_COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    raise ValueError("CONTRACTIQ_AUTH_COOKIE_SAMESITE must be lax, strict, or none")
if AUTH_COOKIE_SAMESITE == "none" and not AUTH_COOKIE_SECURE:
    raise ValueError("Secure authentication cookies are required with SameSite=None")
if ENVIRONMENT in {"production", "prod"} and "*" in ALLOWED_ORIGINS:
    raise ValueError("Wildcard CORS origins are not allowed in production")
if ENVIRONMENT in {"production", "prod"}:
    if len(SECRET_KEY) < 32:
        raise ValueError("CONTRACTIQ_SECRET_KEY must contain at least 32 characters in production")
    if not AUTH_COOKIE_SECURE:
        raise ValueError("CONTRACTIQ_AUTH_COOKIE_SECURE must be true in production")
    if not FRONTEND_BASE_URL.startswith("https://"):
        raise ValueError("CONTRACTIQ_FRONTEND_BASE_URL must use HTTPS in production")
    if not ALLOWED_ORIGINS or any(not origin.startswith("https://") for origin in ALLOWED_ORIGINS):
        raise ValueError("Production CORS origins must use HTTPS")