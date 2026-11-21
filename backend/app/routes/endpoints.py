from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import ApiEndpoint, ApiSpecification
from app.schemas.endpoint import EndpointOut

router = APIRouter(tags=["endpoints"])


@router.get("/api/v1/specifications/{specification_id}/endpoints", response_model=list[EndpointOut])
def list_endpoints(specification_id: UUID, db: Session = Depends(get_db)) -> list[EndpointOut]:
    if not db.get(ApiSpecification, specification_id):
        raise HTTPException(404, "Specification not found.")
    endpoints = db.query(ApiEndpoint).filter(
        ApiEndpoint.specification_id == specification_id
    ).order_by(ApiEndpoint.path, ApiEndpoint.method).all()
    return [EndpointOut.model_validate(endpoint.__dict__) for endpoint in endpoints]
