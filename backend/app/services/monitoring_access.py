import hmac
import logging
from uuid import UUID

from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import MONITORING_ALLOWED_PROJECT_IDS, MONITORING_AUTH_TOKEN
from app.database.models import Project

logger = logging.getLogger(__name__)
WEBSOCKET_SUBPROTOCOL = "contractiq.monitoring.v1"


def token_matches(token: str | None) -> bool:
    return bool(MONITORING_AUTH_TOKEN and token and hmac.compare_digest(token, MONITORING_AUTH_TOKEN))


def require_monitoring_token(authorization: str | None = Header(default=None)) -> None:
    if not MONITORING_AUTH_TOKEN:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Monitoring access is disabled until CONTRACTIQ_MONITORING_AUTH_TOKEN is configured.",
        )
    scheme, separator, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not separator or not token_matches(token.strip()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "A valid monitoring bearer token is required.")


def authorize_monitoring_project(db: Session, project_id: UUID) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    if not MONITORING_ALLOWED_PROJECT_IDS or (
        "*" not in MONITORING_ALLOWED_PROJECT_IDS
        and str(project_id) not in MONITORING_ALLOWED_PROJECT_IDS
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This project is not in CONTRACTIQ_MONITORING_ALLOWED_PROJECT_IDS.",
        )
    return project
