from hashlib import sha256
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Form
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import MAX_UPLOAD_SIZE
from app.database.connection import get_db
from app.database.models import ApiEndpoint, ApiSpecification, Project, User
from app.schemas.specification import SpecificationOut
from app.services.authentication import get_current_user
from app.services.authorization import READ_ROLES, WRITE_ROLES, project_membership, record_project_activity
from app.services.openapi_parser import OpenApiParseError
from app.services.specification_comparison import compare_specifications
from app.services.specification_validator import validate_document
from app.utils.file_validation import UploadValidationError, detect_format

router = APIRouter(tags=["specifications"])


def specification_out(db: Session, specification: ApiSpecification) -> SpecificationOut:
    count = db.query(func.count(ApiEndpoint.id)).filter(
        ApiEndpoint.specification_id == specification.id
    ).scalar() or 0
    return SpecificationOut.model_validate({**specification.__dict__, "endpoint_count": count})


@router.post("/api/v1/projects/{project_id}/specifications/import", status_code=201)
async def import_specification(
    project_id: UUID,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    project_membership(db, user, project_id, WRITE_ROLES)
    if project.is_archived:
        raise HTTPException(409, "Restore this project before importing a specification.")
    content = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"File exceeds the {MAX_UPLOAD_SIZE // (1024 * 1024)} MB upload limit.")
    try:
        file_format, document = detect_format(file.filename or "", content)
    except UploadValidationError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    except UnicodeDecodeError as exc:
        raise HTTPException(400, "The uploaded file must be UTF-8 encoded.") from exc

    try:
        parsed = validate_document(document)
    except OpenApiParseError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc

    content_hash = sha256(content).hexdigest()
    duplicate = db.query(ApiSpecification).filter(
        ApiSpecification.project_id == project_id,
        ApiSpecification.content_hash == content_hash,
    ).first()
    if duplicate:
        raise HTTPException(409, "An identical specification was already imported. Use a deliberate new version to re-import unchanged content.")

    latest = db.query(func.max(ApiSpecification.version_number)).filter(
        ApiSpecification.project_id == project_id
    ).scalar()
    specification = ApiSpecification(
        project_id=project_id,
        title=(title.strip() if title and title.strip() else parsed["title"]),
        description=parsed["description"],
        openapi_version=parsed["openapi_version"],
        api_version=parsed["api_version"],
        original_filename=file.filename or "specification",
        file_format=file_format,
        version_number=(latest or 0) + 1,
        raw_specification=document,
        content_hash=content_hash,
    )
    db.add(specification)
    db.flush()
    try:
        for endpoint in parsed["endpoints"]:
            db.add(ApiEndpoint(specification_id=specification.id, **endpoint))
        record_project_activity(
            db,
            project_id=project_id,
            actor_user_id=user.id,
            action="specification_imported",
            resource_type="specification",
            resource_id=str(specification.id),
            details={"version_number": specification.version_number, "endpoint_count": len(parsed["endpoints"])},
        )
        db.commit()
        db.refresh(specification)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(500, "The specification could not be stored due to a database error.") from exc
    return {
        **specification_out(db, specification).model_dump(),
        "validation_status": "valid",
    }


@router.get("/api/v1/projects/{project_id}/specifications")
def list_specifications(
    project_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SpecificationOut]:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    project_membership(db, user, project_id, READ_ROLES)
    specifications = db.query(ApiSpecification).filter(
        ApiSpecification.project_id == project_id
    ).order_by(ApiSpecification.version_number.desc()).all()
    return [specification_out(db, item) for item in specifications]


@router.get("/api/v1/specifications/{specification_id}", response_model=SpecificationOut)
def get_specification(
    specification_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SpecificationOut:
    specification = db.get(ApiSpecification, specification_id)
    if not specification:
        raise HTTPException(404, "Specification not found.")
    project_membership(db, user, specification.project_id, READ_ROLES)
    return specification_out(db, specification)


@router.get("/api/v1/specifications/{specification_id}/versions")
def get_specification_versions(
    specification_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SpecificationOut]:
    specification = db.get(ApiSpecification, specification_id)
    if not specification:
        raise HTTPException(404, "Specification not found.")
    project_membership(db, user, specification.project_id, READ_ROLES)
    specifications = db.query(ApiSpecification).filter(
        ApiSpecification.project_id == specification.project_id
    ).order_by(ApiSpecification.version_number.desc()).all()
    return [specification_out(db, item) for item in specifications]


@router.get("/api/v1/specifications/{specification_id}/raw")
def get_raw_specification(
    specification_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    specification = db.get(ApiSpecification, specification_id)
    if not specification:
        raise HTTPException(404, "Specification not found.")
    project_membership(db, user, specification.project_id, READ_ROLES)
    return specification.raw_specification


@router.get("/api/v1/specifications/{specification_id}/compare/{other_specification_id}")
def compare_specification_versions(
    specification_id: UUID,
    other_specification_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    before = db.get(ApiSpecification, specification_id)
    after = db.get(ApiSpecification, other_specification_id)
    if not before or not after:
        raise HTTPException(404, "One or both specifications were not found.")
    if before.project_id != after.project_id:
        raise HTTPException(400, "Specifications must belong to the same project.")
    project_membership(db, user, before.project_id, READ_ROLES)
    before_endpoints = db.query(ApiEndpoint).filter(ApiEndpoint.specification_id == before.id).all()
    after_endpoints = db.query(ApiEndpoint).filter(ApiEndpoint.specification_id == after.id).all()
    return {
        "before": {"id": str(before.id), "version_number": before.version_number},
        "after": {"id": str(after.id), "version_number": after.version_number},
        **compare_specifications(before_endpoints, after_endpoints),
    }
