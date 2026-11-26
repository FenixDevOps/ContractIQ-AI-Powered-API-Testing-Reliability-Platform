"""Assign unclaimed legacy projects to an existing account as an operator action."""

import argparse
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

from app.database.connection import SessionLocal
from app.database.models import Project, ProjectMembership, User
from app.services.authorization import record_project_activity


def claim_legacy_projects(owner_email: str, project_ids: list[UUID]) -> int:
    normalized_email = owner_email.strip().lower()
    if not normalized_email:
        raise ValueError("Owner email cannot be blank.")
    if not project_ids:
        raise ValueError("Specify at least one project ID.")
    if len(set(project_ids)) != len(project_ids):
        raise ValueError("Project IDs must be unique.")

    with SessionLocal() as db:
        owner = db.query(User).filter(User.email == normalized_email).first()
        if owner is None or not owner.is_active:
            raise ValueError("An active account with the owner email must already exist.")
        projects = db.query(Project).filter(Project.id.in_(project_ids)).all()
        if len(projects) != len(project_ids):
            raise ValueError("One or more project IDs do not exist.")
        existing_memberships = db.query(ProjectMembership.project_id).filter(
            ProjectMembership.project_id.in_(project_ids)
        ).all()
        if existing_memberships:
            raise ValueError("Every selected project must be unclaimed before assignment.")

        for project in projects:
            db.add(ProjectMembership(
                project_id=project.id,
                user_id=owner.id,
                role="OWNER",
            ))
            record_project_activity(
                db,
                project_id=project.id,
                actor_user_id=owner.id,
                action="legacy_project_claimed",
                resource_type="project",
                resource_id=str(project.id),
            )
        db.commit()
        return len(projects)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-email", required=True, help="Existing active account to receive ownership")
    parser.add_argument(
        "--project-id",
        action="append",
        required=True,
        type=UUID,
        help="UUID of an unclaimed project; repeat for each project",
    )
    arguments = parser.parse_args()
    try:
        count = claim_legacy_projects(arguments.owner_email, arguments.project_id)
    except ValueError as error:
        parser.error(str(error))
    print(f"Assigned {count} project(s) to {arguments.owner_email.strip().lower()}.")


if __name__ == "__main__":
    main()
