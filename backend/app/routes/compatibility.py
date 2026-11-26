"""Persisted API compatibility comparison endpoints."""

import json
import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.database.connection import get_db
from app.database.models import (
    ApiSpecification,
    CompatibilityChange,
    CompatibilityComparison,
    Project,
)
from app.schemas.compatibility import ComparisonCreate
from app.services.compatibility_engine import CompatibilityEngine

router = APIRouter(tags=["compatibility"])
logger = logging.getLogger(__name__)


def _comparison(db: Session, comparison_id: UUID) -> CompatibilityComparison:
    item = db.query(CompatibilityComparison).options(
        selectinload(CompatibilityComparison.changes)
    ).filter(CompatibilityComparison.id == comparison_id).first()
    if not item:
        raise HTTPException(404, "Compatibility comparison not found.")
    return item


def _serialize_change(item: CompatibilityChange) -> dict:
    return {
        "id": str(item.id),
        "category": item.category,
        "change_type": item.change_type,
        "severity": item.severity,
        "compatibility": item.compatibility,
        "path": item.path,
        "method": item.method,
        "property_name": item.property_name,
        "old_value": item.old_value,
        "new_value": item.new_value,
        "explanation": item.explanation,
        "recommendation": item.recommendation,
    }


def _serialize_comparison(item: CompatibilityComparison) -> dict:
    return {
        "id": str(item.id),
        "project_id": str(item.project_id),
        "old_specification_id": str(item.old_specification_id),
        "new_specification_id": str(item.new_specification_id),
        "compatibility_score": item.compatibility_score,
        "overall_status": item.overall_status,
        "total_changes": item.total_changes,
        "breaking_changes": item.breaking_changes,
        "non_breaking_changes": item.non_breaking_changes,
        "potentially_breaking_changes": item.potentially_breaking_changes,
        "informational_changes": item.informational_changes,
        "comparison_metadata": item.comparison_metadata,
        "created_at": item.created_at,
    }


@router.post("/api/v1/compatibility/compare", status_code=status.HTTP_201_CREATED)
def create_comparison(payload: ComparisonCreate, db: Session = Depends(get_db)) -> dict:
    old_spec = db.get(ApiSpecification, payload.old_specification_id)
    new_spec = db.get(ApiSpecification, payload.new_specification_id)
    if not old_spec or not new_spec:
        raise HTTPException(404, "One or both specifications were not found.")
    if old_spec.project_id != new_spec.project_id:
        raise HTTPException(400, "Specifications must belong to the same project.")
    if old_spec.id == new_spec.id:
        raise HTTPException(422, "Choose two different specifications.")
    project = db.get(Project, old_spec.project_id)
    if not project:
        raise HTTPException(404, "Project not found.")

    result = CompatibilityEngine().compare(old_spec.raw_specification, new_spec.raw_specification)
    counts = result["counts"]
    metadata = {
        "project_name": project.name,
        "api_name": old_spec.title,
        "old_version": old_spec.api_version,
        "new_version": new_spec.api_version,
        "old_version_number": old_spec.version_number,
        "new_version_number": new_spec.version_number,
        "endpoint_summary": result["endpoint_summary"],
        "score_note": "Indicative heuristic only; not a compatibility guarantee.",
        "score_algorithm": "max(0, 100 - sum of per-change severity penalties)",
        "limitations": [
            "The score is an indicative heuristic, not a mathematically proven compatibility guarantee.",
            "External references are not fetched. Circular or unresolved local references limit comparison at that schema node.",
        ],
    }
    comparison = CompatibilityComparison(
        id=uuid4(),
        project_id=project.id,
        old_specification_id=old_spec.id,
        new_specification_id=new_spec.id,
        compatibility_score=result["compatibility_score"],
        overall_status=result["overall_status"],
        total_changes=len(result["changes"]),
        breaking_changes=counts["breaking"],
        non_breaking_changes=counts["non_breaking"],
        potentially_breaking_changes=counts["potentially_breaking"],
        informational_changes=counts["informational"],
        comparison_metadata=metadata,
    )
    db.add(comparison)
    for change in result["changes"]:
        db.add(CompatibilityChange(
            comparison_id=comparison.id,
            id=UUID(change["id"]),
            **{key: value for key, value in change.items() if key != "id"},
        ))
    try:
        db.commit()
        db.refresh(comparison)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Could not persist compatibility comparison.")
        raise HTTPException(500, "The compatibility comparison could not be stored.") from exc

    return _serialize_comparison(comparison)


@router.get("/api/v1/projects/{project_id}/compatibility")
def get_history(
    project_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found.")
    query = db.query(CompatibilityComparison).filter(
        CompatibilityComparison.project_id == project_id
    )
    total = query.count()
    aggregates = db.query(
        func.coalesce(func.sum(CompatibilityComparison.breaking_changes), 0),
        func.coalesce(func.sum(CompatibilityComparison.non_breaking_changes), 0),
        func.coalesce(func.sum(CompatibilityComparison.potentially_breaking_changes), 0),
        func.coalesce(func.avg(CompatibilityComparison.compatibility_score), 0),
    ).filter(CompatibilityComparison.project_id == project_id).one()
    items = query.order_by(CompatibilityComparison.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "items": [_serialize_comparison(item) for item in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "summary": {
            "comparisons": total,
            "breaking_changes": int(aggregates[0]),
            "non_breaking_changes": int(aggregates[1]),
            "potentially_breaking_changes": int(aggregates[2]),
            "average_compatibility_score": round(float(aggregates[3]), 1),
        },
    }


@router.get("/api/v1/compatibility/{comparison_id}")
def get_comparison(comparison_id: UUID, db: Session = Depends(get_db)) -> dict:
    item = _comparison(db, comparison_id)
    return {
        **_serialize_comparison(item),
        "changes": [_serialize_change(change) for change in item.changes],
    }


@router.get("/api/v1/compatibility/{comparison_id}/changes")
def get_changes(
    comparison_id: UUID,
    severity: str | None = Query(
        None, pattern=r"(?i)^(CRITICAL|HIGH|MEDIUM|LOW|INFO)$"
    ),
    compatibility: str | None = Query(
        None, pattern=r"(?i)^(BREAKING|NON_BREAKING|POTENTIALLY_BREAKING|INFORMATIONAL)$"
    ),
    category: str | None = Query(
        None, pattern=r"(?i)^(ENDPOINT|PARAMETER|REQUEST_BODY|RESPONSE|RESPONSE_SCHEMA|SECURITY|CONTENT_TYPE)$"
    ),
    method: str | None = Query(
        None, pattern=r"(?i)^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|TRACE)$"
    ),
    path: str | None = Query(None, max_length=2048),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    if not db.get(CompatibilityComparison, comparison_id):
        raise HTTPException(404, "Compatibility comparison not found.")
    query = db.query(CompatibilityChange).filter(
        CompatibilityChange.comparison_id == comparison_id
    )
    for value, column in (
        (severity, CompatibilityChange.severity),
        (compatibility, CompatibilityChange.compatibility),
        (category, CompatibilityChange.category),
    ):
        if value:
            query = query.filter(column == value.strip().upper())
    if method:
        query = query.filter(CompatibilityChange.method == method.strip().upper())
    if path:
        query = query.filter(CompatibilityChange.path.contains(path.strip(), autoescape=True))
    total = query.count()
    items = query.order_by(CompatibilityChange.created_at, CompatibilityChange.id).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "items": [_serialize_change(item) for item in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/api/v1/compatibility/{comparison_id}/summary")
def get_summary(comparison_id: UUID, db: Session = Depends(get_db)) -> dict:
    item = _comparison(db, comparison_id)
    return {
        **_serialize_comparison(item),
        "endpoint_summary": item.comparison_metadata.get("endpoint_summary", {}),
        "score_note": item.comparison_metadata.get("score_note"),
        "limitations": item.comparison_metadata.get("limitations", []),
    }


@router.get("/api/v1/compatibility/{comparison_id}/report/json")
def download_json_report(comparison_id: UUID, db: Session = Depends(get_db)) -> Response:
    item = _comparison(db, comparison_id)
    old_spec = db.get(ApiSpecification, item.old_specification_id)
    new_spec = db.get(ApiSpecification, item.new_specification_id)
    project = db.get(Project, item.project_id)
    report = {
        **_serialize_comparison(item),
        "project_name": project.name if project else None,
        "api_name": old_spec.title if old_spec else None,
        "previous_specification": {
            "id": str(old_spec.id), "api_version": old_spec.api_version,
            "version_number": old_spec.version_number,
        } if old_spec else None,
        "new_specification": {
            "id": str(new_spec.id), "api_version": new_spec.api_version,
            "version_number": new_spec.version_number,
        } if new_spec else None,
        "changes": [_serialize_change(change) for change in item.changes],
    }
    content = json.dumps(report, ensure_ascii=True, separators=(",", ":"), default=str)
    filename = f"contractiq-compatibility-{item.id}.json"
    return JSONResponse(
        content=json.loads(content),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/api/v1/compatibility/{comparison_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comparison(comparison_id: UUID, db: Session = Depends(get_db)) -> Response:
    item = db.get(CompatibilityComparison, comparison_id)
    if not item:
        raise HTTPException(404, "Compatibility comparison not found.")
    db.delete(item)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Could not delete compatibility comparison.")
        raise HTTPException(500, "The compatibility comparison could not be deleted.") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
