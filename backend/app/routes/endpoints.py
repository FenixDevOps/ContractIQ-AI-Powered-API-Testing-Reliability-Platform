from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import ApiEndpoint, ApiSpecification, User
from app.schemas.endpoint import EndpointOut
from app.services.authentication import get_current_user
from app.services.authorization import READ_ROLES, project_membership

router = APIRouter(tags=["endpoints"])


@router.get("/api/v1/specifications/{specification_id}/endpoints", response_model=list[EndpointOut])
def list_endpoints(
    specification_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[EndpointOut]:
    specification = db.get(ApiSpecification, specification_id)
    if not specification:
        raise HTTPException(404, "Specification not found.")
    project_membership(db, user, specification.project_id, READ_ROLES)
    endpoints = db.query(ApiEndpoint).filter(
        ApiEndpoint.specification_id == specification_id
    ).order_by(ApiEndpoint.path, ApiEndpoint.method).all()
    return [EndpointOut.model_validate(endpoint.__dict__) for endpoint in endpoints]
