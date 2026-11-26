"""Project membership checks and audit helpers."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database.models import (
    ApiSpecification,
    Project,
    ProjectActivity,
    ProjectMembership,
    User,
)

READ_ROLES = frozenset({"OWNER", "ADMIN", "MEMBER", "VIEWER"})
WRITE_ROLES = frozenset({"OWNER", "ADMIN", "MEMBER"})
MANAGE_ROLES = frozenset({"OWNER", "ADMIN"})
OWNER_ROLES = frozenset({"OWNER"})


def project_membership(
    db: Session,
    user: User,
    project_id: UUID,
    allowed_roles: frozenset[str] = READ_ROLES,
) -> tuple[Project, ProjectMembership]:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == project_id,
        ProjectMembership.user_id == user.id,
    ).first()
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    if membership.role not in allowed_roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your project role does not allow this action.")
    return project, membership


def specification_access(
    db: Session,
    user: User,
    specification_id: UUID,
    allowed_roles: frozenset[str] = READ_ROLES,
) -> ApiSpecification:
    specification = db.get(ApiSpecification, specification_id)
    if specification is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Specification not found.")
    project_membership(db, user, specification.project_id, allowed_roles)
    return specification


def record_project_activity(
    db: Session,
    *,
    project_id: UUID,
    actor_user_id: UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
) -> None:
    db.add(ProjectActivity(
        project_id=project_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
    ))
