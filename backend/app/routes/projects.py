from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import ApiEndpoint, ApiSpecification, Project
from app.schemas.project import ProjectCreate, ProjectOut

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectOut:
    project = Project(name=payload.name.strip(), description=payload.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectOut.model_validate({**project.__dict__, "specification_count": 0, "latest_version": None, "endpoint_count": 0})


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectOut]:
    projects = db.query(Project).order_by(Project.updated_at.desc()).all()
    result = []
    for project in projects:
        specifications = db.query(ApiSpecification).filter(ApiSpecification.project_id == project.id).all()
        latest = max((item.version_number for item in specifications), default=None)
        endpoint_count = db.query(func.count(ApiEndpoint.id)).join(
            ApiSpecification, ApiEndpoint.specification_id == ApiSpecification.id
        ).filter(ApiSpecification.project_id == project.id).scalar() or 0
        result.append(ProjectOut.model_validate({
            **project.__dict__,
            "specification_count": len(specifications),
            "latest_version": latest,
            "endpoint_count": endpoint_count,
        }))
    return result


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: UUID, db: Session = Depends(get_db)) -> ProjectOut:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    specifications = db.query(ApiSpecification).filter(ApiSpecification.project_id == project.id).all()
    latest = max((item.version_number for item in specifications), default=None)
    endpoint_count = db.query(func.count(ApiEndpoint.id)).join(
        ApiSpecification, ApiEndpoint.specification_id == ApiSpecification.id
    ).filter(ApiSpecification.project_id == project.id).scalar() or 0
    return ProjectOut.model_validate({
        **project.__dict__,
        "specification_count": len(specifications),
        "latest_version": latest,
        "endpoint_count": endpoint_count,
    })
