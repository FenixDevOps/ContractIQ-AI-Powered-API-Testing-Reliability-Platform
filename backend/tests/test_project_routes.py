import re
from uuid import UUID

from app.database.connection import get_db
from app.database.models import ProjectMembership, User
from app.main import app
from app.services.authentication import get_current_user, hash_password


def _create_user(email, full_name):
    session_generator = app.dependency_overrides[get_db]()
    db = next(session_generator)
    try:
        user = User(
            full_name=full_name,
            email=email,
            hashed_password=hash_password("test-user-password-123"),
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        session_generator.close()


def test_viewer_can_read_project_but_cannot_write_or_manage(isolated_client):
    project = isolated_client.post(
        "/api/v1/projects",
        json={"name": "Viewer project", "description": "Role boundary"},
    ).json()
    viewer = _create_user("viewer@example.com", "Project Viewer")

    session_generator = app.dependency_overrides[get_db]()
    db = next(session_generator)
    try:
        db.add(ProjectMembership(
            project_id=UUID(project["id"]),
            user_id=viewer.id,
            role="VIEWER",
        ))
        db.commit()
    finally:
        session_generator.close()

    app.dependency_overrides[get_current_user] = lambda: viewer
    try:
        assert isolated_client.get(f"/api/v1/projects/{project['id']}").status_code == 200
        assert isolated_client.patch(
            f"/api/v1/projects/{project['id']}",
            json={"name": "Changed"},
        ).status_code == 403
        assert isolated_client.post(f"/api/v1/projects/{project['id']}/archive").status_code == 403
        assert isolated_client.get("/api/v1/projects").json()[0]["current_user_role"] == "VIEWER"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_project_invitation_is_bound_to_email_and_single_use(isolated_client, monkeypatch):
    import app.routes.projects as project_routes

    project = isolated_client.post(
        "/api/v1/projects",
        json={"name": "Invitation project"},
    ).json()
    messages = []
    monkeypatch.setattr(project_routes, "email_delivery_configured", lambda: True)
    monkeypatch.setattr(
        project_routes,
        "send_security_email",
        lambda recipient, subject, body: messages.append((recipient, subject, body)),
    )
    invitation = isolated_client.post(
        f"/api/v1/projects/{project['id']}/invites",
        json={"email": "invited@example.com", "role": "MEMBER"},
    )
    assert invitation.status_code == 201, invitation.text
    assert messages[0][0] == "invited@example.com"
    token = re.search(r"invite_token=([^\s&]+)", messages[0][2]).group(1)

    invited_user = _create_user("invited@example.com", "Invited User")
    other_user = _create_user("other@example.com", "Other User")
    app.dependency_overrides[get_current_user] = lambda: other_user
    try:
        rejected = isolated_client.post(
            "/api/v1/projects/invites/accept",
            json={"token": token},
        )
        assert rejected.status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    app.dependency_overrides[get_current_user] = lambda: invited_user
    try:
        accepted = isolated_client.post(
            "/api/v1/projects/invites/accept",
            json={"token": token},
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["current_user_role"] == "MEMBER"
        assert isolated_client.post(
            "/api/v1/projects/invites/accept",
            json={"token": token},
        ).status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_user, None)
