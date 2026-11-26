"""Project, membership, invitation, and activity APIs."""

import secrets
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import FRONTEND_BASE_URL
from app.database.connection import get_db
from app.database.models import (
    ApiEndpoint,
    ApiSpecification,
    CompatibilityComparison,
    MonitoringAlert,
    MonitoringConfiguration,
    Project,
    ProjectActivity,
    ProjectInvite,
    ProjectMembership,
    TestResult,
    TestRun,
    User,
)
from app.schemas.project import (
    ProjectActivityOut,
    ProjectCreate,
    ProjectInviteAccept,
    ProjectInviteCreate,
    ProjectInviteOut,
    ProjectMemberOut,
    ProjectOut,
    ProjectRoleUpdate,
    ProjectUpdate,
)
from app.services.authentication import hash_opaque_token, utc_now
from app.services.authentication import get_current_user
from app.services.authorization import (
    MANAGE_ROLES,
    OWNER_ROLES,
    READ_ROLES,
    WRITE_ROLES,
    project_membership,
    record_project_activity,
)
from app.services.email_delivery import EmailDeliveryError, email_delivery_configured, send_security_email

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _project_output(
    db: Session,
    project: Project,
    membership: ProjectMembership,
) -> ProjectOut:
    specifications = db.query(ApiSpecification).filter(
        ApiSpecification.project_id == project.id
    ).all()
    latest = max((item.version_number for item in specifications), default=None)
    endpoint_count = db.query(func.count(ApiEndpoint.id)).join(
        ApiSpecification, ApiEndpoint.specification_id == ApiSpecification.id
    ).filter(ApiSpecification.project_id == project.id).scalar() or 0
    owner = db.query(ProjectMembership.user_id).filter(
        ProjectMembership.project_id == project.id,
        ProjectMembership.role == "OWNER",
    ).first()
    return ProjectOut.model_validate({
        **project.__dict__,
        "owner_id": owner[0] if owner else None,
        "current_user_role": membership.role,
        "specification_count": len(specifications),
        "latest_version": latest,
        "endpoint_count": endpoint_count,
    })


def _activity_output(db: Session, item: ProjectActivity) -> ProjectActivityOut:
    actor = db.get(User, item.actor_user_id) if item.actor_user_id else None
    return ProjectActivityOut(
        id=item.id,
        actor_name=actor.full_name if actor else None,
        action=item.action,
        resource_type=item.resource_type,
        resource_id=item.resource_id,
        details=item.details,
        created_at=item.created_at,
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    project = Project(name=payload.name, description=payload.description.strip() if payload.description else None)
    db.add(project)
    db.flush()
    membership = ProjectMembership(project_id=project.id, user_id=user.id, role="OWNER")
    db.add(membership)
    record_project_activity(
        db,
        project_id=project.id,
        actor_user_id=user.id,
        action="project_created",
        resource_type="project",
        resource_id=str(project.id),
    )
    db.commit()
    db.refresh(project)
    db.refresh(membership)
    return _project_output(db, project, membership)


@router.get("", response_model=list[ProjectOut])
def list_projects(
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProjectOut]:
    memberships = db.query(ProjectMembership, Project).join(
        Project, Project.id == ProjectMembership.project_id
    ).filter(ProjectMembership.user_id == user.id)
    if not include_archived:
        memberships = memberships.filter(Project.is_archived.is_(False))
    return [
        _project_output(db, project, membership)
        for membership, project in memberships.order_by(Project.updated_at.desc()).all()
    ]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    project, membership = project_membership(db, user, project_id)
    return _project_output(db, project, membership)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    project, membership = project_membership(db, user, project_id, WRITE_ROLES)
    if project.is_archived:
        raise HTTPException(status.HTTP_409_CONFLICT, "Restore this project before editing it.")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("name") is not None:
        project.name = changes["name"]
    if "description" in changes:
        project.description = changes["description"].strip() if changes["description"] else None
    record_project_activity(
        db,
        project_id=project.id,
        actor_user_id=user.id,
        action="project_updated",
        resource_type="project",
        resource_id=str(project.id),
        details={"fields": sorted(changes)},
    )
    db.commit()
    db.refresh(project)
    return _project_output(db, project, membership)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: UUID,
    confirm: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    project, _ = project_membership(db, user, project_id, OWNER_ROLES)
    if not confirm:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Set confirm=true to permanently delete the project.")
    db.delete(project)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{project_id}/archive", response_model=ProjectOut)
def archive_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    project, membership = project_membership(db, user, project_id, MANAGE_ROLES)
    if not project.is_archived:
        project.is_archived = True
        project.archived_at = utc_now()
        db.query(MonitoringConfiguration).filter(
            MonitoringConfiguration.project_id == project.id
        ).update({MonitoringConfiguration.enabled: False}, synchronize_session=False)
        record_project_activity(
            db,
            project_id=project.id,
            actor_user_id=user.id,
            action="project_archived",
            resource_type="project",
            resource_id=str(project.id),
        )
        db.commit()
        db.refresh(project)
    return _project_output(db, project, membership)


@router.post("/{project_id}/restore", response_model=ProjectOut)
def restore_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    project, membership = project_membership(db, user, project_id, MANAGE_ROLES)
    if project.is_archived:
        project.is_archived = False
        project.archived_at = None
        record_project_activity(
            db,
            project_id=project.id,
            actor_user_id=user.id,
            action="project_restored",
            resource_type="project",
            resource_id=str(project.id),
        )
        db.commit()
        db.refresh(project)
    return _project_output(db, project, membership)


@router.get("/{project_id}/members", response_model=list[ProjectMemberOut])
def list_project_members(
    project_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProjectMemberOut]:
    project_membership(db, user, project_id, READ_ROLES)
    rows = db.query(ProjectMembership, User).join(
        User, User.id == ProjectMembership.user_id
    ).filter(
        ProjectMembership.project_id == project_id
    ).order_by(ProjectMembership.created_at, User.email).all()
    return [
        ProjectMemberOut(
            user_id=member.user_id,
            full_name=member_user.full_name,
            email=member_user.email,
            role=member.role,
            joined_at=member.created_at,
        )
        for member, member_user in rows
    ]


@router.post("/{project_id}/invites", response_model=ProjectInviteOut, status_code=status.HTTP_201_CREATED)
def invite_project_member(
    project_id: UUID,
    payload: ProjectInviteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectInviteOut:
    project, actor_membership = project_membership(db, user, project_id, MANAGE_ROLES)
    if project.is_archived:
        raise HTTPException(status.HTTP_409_CONFLICT, "Restore this project before inviting members.")
    if actor_membership.role != "OWNER" and payload.role == "ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the project owner can invite an administrator.")
    if not email_delivery_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Invitation email delivery is not configured.")

    email = str(payload.email).strip().lower()
    invited_user = db.query(User).filter(User.email == email).first()
    if invited_user and db.query(ProjectMembership.id).filter(
        ProjectMembership.project_id == project_id,
        ProjectMembership.user_id == invited_user.id,
    ).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "This user is already a project member.")
    pending = db.query(ProjectInvite.id).filter(
        ProjectInvite.project_id == project_id,
        ProjectInvite.email == email,
        ProjectInvite.accepted_at.is_(None),
        ProjectInvite.expires_at > utc_now(),
    ).first()
    if pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "A pending invitation already exists for this email.")

    token = secrets.token_urlsafe(32)
    invite = ProjectInvite(
        project_id=project.id,
        invited_by_user_id=user.id,
        email=email,
        role=payload.role,
        token_hash=hash_opaque_token(token),
        expires_at=utc_now() + timedelta(days=7),
    )
    db.add(invite)
    record_project_activity(
        db,
        project_id=project.id,
        actor_user_id=user.id,
        action="member_invited",
        resource_type="invitation",
        details={"email": email, "role": payload.role},
    )
    db.commit()
    db.refresh(invite)
    invite_url = (
        f"{FRONTEND_BASE_URL}/#invite_token={token}"
        f"&project_id={project.id}"
    )
    try:
        send_security_email(
            email,
            f"Invitation to join {project.name} on ContractIQ",
            f"You have been invited to join {project.name} as {payload.role}. "
            f"Sign in or create an account with this email, then accept the invitation:\n\n{invite_url}\n\n"
            "This invitation expires in seven days.",
        )
    except EmailDeliveryError as exc:
        db.query(ProjectInvite).filter(ProjectInvite.id == invite.id).delete()
        db.commit()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The invitation could not be delivered. Check SMTP configuration and try again.",
        ) from exc
    return ProjectInviteOut.model_validate(invite)


@router.get("/{project_id}/invites", response_model=list[ProjectInviteOut])
def list_project_invites(
    project_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProjectInviteOut]:
    project_membership(db, user, project_id, MANAGE_ROLES)
    invitations = db.query(ProjectInvite).filter(
        ProjectInvite.project_id == project_id,
        ProjectInvite.accepted_at.is_(None),
        ProjectInvite.expires_at > utc_now(),
    ).order_by(ProjectInvite.created_at.desc()).all()
    return [ProjectInviteOut.model_validate(item) for item in invitations]


@router.delete("/{project_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_project_invite(
    project_id: UUID,
    invite_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    project_membership(db, user, project_id, MANAGE_ROLES)
    invite = db.get(ProjectInvite, invite_id)
    if invite is None or invite.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found.")
    db.delete(invite)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/invites/accept", response_model=ProjectOut)
def accept_project_invite(
    payload: ProjectInviteAccept,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    invite = db.query(ProjectInvite).filter(
        ProjectInvite.token_hash == hash_opaque_token(payload.token),
        ProjectInvite.accepted_at.is_(None),
        ProjectInvite.expires_at > utc_now(),
    ).with_for_update().first()
    if invite is None or invite.email != user.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invitation is invalid or expired.")
    project = db.get(Project, invite.project_id)
    if project is None or project.is_archived:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invitation is invalid or expired.")
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == project.id,
        ProjectMembership.user_id == user.id,
    ).first()
    if membership:
        raise HTTPException(status.HTTP_409_CONFLICT, "You are already a member of this project.")
    membership = ProjectMembership(project_id=project.id, user_id=user.id, role=invite.role)
    invite.accepted_at = utc_now()
    db.add(membership)
    record_project_activity(
        db,
        project_id=project.id,
        actor_user_id=user.id,
        action="member_joined",
        resource_type="membership",
        resource_id=str(user.id),
        details={"role": invite.role},
    )
    db.commit()
    db.refresh(membership)
    return _project_output(db, project, membership)


@router.patch("/{project_id}/members/{member_user_id}")
def change_member_role(
    project_id: UUID,
    member_user_id: UUID,
    payload: ProjectRoleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    project, actor_membership = project_membership(db, user, project_id, MANAGE_ROLES)
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == project_id,
        ProjectMembership.user_id == member_user_id,
    ).first()
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project member not found.")
    if membership.role == "OWNER":
        raise HTTPException(status.HTTP_409_CONFLICT, "Transfer project ownership before changing the owner role.")
    if actor_membership.role != "OWNER" and (
        membership.role == "ADMIN" or payload.role == "ADMIN"
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the project owner can manage administrators.")
    membership.role = payload.role
    record_project_activity(
        db,
        project_id=project.id,
        actor_user_id=user.id,
        action="member_role_changed",
        resource_type="membership",
        resource_id=str(member_user_id),
        details={"role": payload.role},
    )
    db.commit()
    return {"user_id": str(member_user_id), "role": membership.role}


@router.delete("/{project_id}/members/{member_user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_member(
    project_id: UUID,
    member_user_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    project, actor_membership = project_membership(db, user, project_id, MANAGE_ROLES)
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == project_id,
        ProjectMembership.user_id == member_user_id,
    ).first()
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project member not found.")
    if membership.role == "OWNER":
        raise HTTPException(status.HTTP_409_CONFLICT, "Transfer project ownership before removing the owner.")
    if actor_membership.role != "OWNER" and membership.role == "ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the project owner can remove an administrator.")
    record_project_activity(
        db,
        project_id=project.id,
        actor_user_id=user.id,
        action="member_removed",
        resource_type="membership",
        resource_id=str(member_user_id),
    )
    db.delete(membership)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{project_id}/transfer-ownership")
def transfer_ownership(
    project_id: UUID,
    new_owner_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    project, actor_membership = project_membership(db, user, project_id, OWNER_ROLES)
    new_owner = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == project_id,
        ProjectMembership.user_id == new_owner_id,
    ).first()
    if new_owner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project member not found.")
    if new_owner.user_id == user.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose another project member.")
    new_owner.role = "OWNER"
    actor_membership.role = "ADMIN"
    record_project_activity(
        db,
        project_id=project.id,
        actor_user_id=user.id,
        action="ownership_transferred",
        resource_type="membership",
        resource_id=str(new_owner_id),
    )
    db.commit()
    return {"owner_id": str(new_owner_id)}


@router.get("/{project_id}/activity", response_model=list[ProjectActivityOut])
def project_activity(
    project_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProjectActivityOut]:
    project_membership(db, user, project_id, READ_ROLES)
    activities = db.query(ProjectActivity).filter(
        ProjectActivity.project_id == project_id,
    ).order_by(
        ProjectActivity.created_at.desc(),
        ProjectActivity.id.desc(),
    ).offset((page - 1) * page_size).limit(page_size).all()
    return [_activity_output(db, item) for item in activities]


@router.get("/{project_id}/dashboard")
def project_dashboard(
    project_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    project, membership = project_membership(db, user, project_id, READ_ROLES)
    specification_query = db.query(ApiSpecification).filter(
        ApiSpecification.project_id == project.id
    )
    specification_ids = [item[0] for item in specification_query.with_entities(ApiSpecification.id).all()]
    endpoint_count = db.query(func.count(ApiEndpoint.id)).join(
        ApiSpecification, ApiSpecification.id == ApiEndpoint.specification_id
    ).filter(ApiSpecification.project_id == project.id).scalar() or 0
    test_run_query = db.query(TestRun).filter(TestRun.specification_id.in_(specification_ids))
    test_run_count = test_run_query.count() if specification_ids else 0
    latest_runs = test_run_query.order_by(TestRun.started_at.desc()).limit(5).all() if specification_ids else []
    comparison_query = db.query(CompatibilityComparison).filter(
        CompatibilityComparison.project_id == project.id
    )
    total_breaking = db.query(func.coalesce(func.sum(CompatibilityComparison.breaking_changes), 0)).filter(
        CompatibilityComparison.project_id == project.id
    ).scalar() or 0
    active_alerts = db.query(func.count(MonitoringAlert.id)).filter(
        MonitoringAlert.project_id == project.id,
        MonitoringAlert.status.in_(("OPEN", "ACKNOWLEDGED")),
    ).scalar() or 0
    enabled_monitors = db.query(func.count(MonitoringConfiguration.id)).filter(
        MonitoringConfiguration.project_id == project.id,
        MonitoringConfiguration.enabled.is_(True),
    ).scalar() or 0
    recent_activity = db.query(ProjectActivity).filter(
        ProjectActivity.project_id == project.id,
    ).order_by(ProjectActivity.created_at.desc()).limit(10).all()
    latest_run_ids = [item.id for item in latest_runs]
    latest_results = db.query(TestResult.status, func.count(TestResult.id)).join(
        TestRun, TestRun.id == TestResult.test_run_id
    ).filter(TestRun.id.in_(latest_run_ids)).group_by(TestResult.status).all() if latest_run_ids else []

    return {
        "project": _project_output(db, project, membership).model_dump(mode="json"),
        "specification_count": len(specification_ids),
        "endpoint_count": endpoint_count,
        "test_run_count": test_run_count,
        "latest_test_runs": [
            {
                "id": str(item.id),
                "status": item.status,
                "started_at": item.started_at.isoformat(),
                "total_tests": item.total_tests,
                "passed_tests": item.passed_tests,
                "failed_tests": item.failed_tests,
            }
            for item in latest_runs
        ],
        "latest_test_result_counts": {key: value for key, value in latest_results},
        "compatibility_comparison_count": comparison_query.count(),
        "breaking_changes_detected": int(total_breaking),
        "enabled_monitoring_configurations": enabled_monitors,
        "active_alert_count": active_alerts,
        "recent_activity": [_activity_output(db, item).model_dump(mode="json") for item in recent_activity],
    }
