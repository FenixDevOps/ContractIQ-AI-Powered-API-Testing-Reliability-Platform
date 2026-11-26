import re
from datetime import datetime, timedelta, timezone

import jwt

from app.config import SECRET_KEY
from app.database.connection import get_db
from app.database.models import EmailVerificationToken, Project, ProjectMembership, User
from app.main import app


def _register(client, *, email="new-user@example.com", password="correct-horse-battery-9"):
    return client.post(
        "/api/v1/auth/register",
        json={"full_name": "  New   User ", "email": email, "password": password},
    )


def test_registration_hashes_password_and_returns_minimal_user(auth_client):
    response = _register(auth_client)

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["user"]["full_name"] == "New User"
    assert payload["user"]["email"] == "new-user@example.com"
    assert "hashed_password" not in payload["user"]
    assert "refresh_token" not in payload
    assert auth_client.cookies.get("contractiq_refresh")
    assert auth_client.cookies.get("contractiq_csrf")

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "new-user@example.com", "password": "correct-horse-battery-9"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["id"] == payload["user"]["id"]


def test_email_verification_is_required_hashed_and_single_use(auth_client, monkeypatch):
    import app.routes.auth as auth_routes

    monkeypatch.setattr(auth_routes, "AUTH_REQUIRE_EMAIL_VERIFICATION", True)
    monkeypatch.setattr(auth_routes, "email_delivery_configured", lambda: True)
    messages = []
    monkeypatch.setattr(
        auth_routes,
        "send_security_email",
        lambda recipient, subject, body: messages.append((recipient, subject, body)),
    )

    registration = _register(auth_client, email="verify-user@example.com")
    assert registration.status_code == 201, registration.text
    assert registration.json()["message"].startswith("Check your email")
    assert auth_client.cookies.get("contractiq_refresh") is None
    assert auth_client.post(
        "/api/v1/auth/login",
        json={"email": "verify-user@example.com", "password": "correct-horse-battery-9"},
    ).status_code == 403

    token = re.search(r"verify_token=([^\s&]+)", messages[0][2]).group(1)
    session_generator = app.dependency_overrides[get_db]()
    db = next(session_generator)
    try:
        token_record = db.query(EmailVerificationToken).one()
        assert token_record.token_hash != token
    finally:
        session_generator.close()

    confirmation = auth_client.post(
        "/api/v1/auth/email-verification/confirm",
        json={"token": token},
    )
    assert confirmation.status_code == 200
    assert confirmation.json()["message"] == "Email verified. You can now sign in."
    assert auth_client.post(
        "/api/v1/auth/email-verification/confirm",
        json={"token": token},
    ).status_code == 400
    assert auth_client.post(
        "/api/v1/auth/login",
        json={"email": "verify-user@example.com", "password": "correct-horse-battery-9"},
    ).status_code == 200


def test_registration_requires_email_delivery_when_verification_is_enabled(auth_client, monkeypatch):
    import app.routes.auth as auth_routes

    monkeypatch.setattr(auth_routes, "AUTH_REQUIRE_EMAIL_VERIFICATION", True)
    monkeypatch.setattr(auth_routes, "email_delivery_configured", lambda: False)

    response = _register(auth_client, email="no-mail-user@example.com")

    assert response.status_code == 503
    session_generator = app.dependency_overrides[get_db]()
    db = next(session_generator)
    try:
        assert db.query(User).filter(User.email == "no-mail-user@example.com").first() is None
    finally:
        session_generator.close()


def test_email_verification_resend_does_not_disclose_account_existence(auth_client, monkeypatch):
    import app.routes.auth as auth_routes

    assert _register(auth_client, email="resend-user@example.com").status_code == 201
    monkeypatch.setattr(auth_routes, "email_delivery_configured", lambda: True)
    messages = []
    monkeypatch.setattr(
        auth_routes,
        "send_security_email",
        lambda recipient, subject, body: messages.append((recipient, subject, body)),
    )

    known = auth_client.post(
        "/api/v1/auth/email-verification/request",
        json={"email": "resend-user@example.com"},
    )
    unknown = auth_client.post(
        "/api/v1/auth/email-verification/request",
        json={"email": "missing-user@example.com"},
    )

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(messages) == 1


def test_unverified_access_and_refresh_sessions_are_rejected_when_enforced(auth_client, monkeypatch):
    import app.services.authentication as authentication

    registration = _register(auth_client, email="existing-session@example.com")
    assert registration.status_code == 201
    csrf_token = auth_client.cookies.get("contractiq_csrf")
    monkeypatch.setattr(authentication, "AUTH_REQUIRE_EMAIL_VERIFICATION", True)

    access = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {registration.json()['access_token']}"},
    )
    refresh = auth_client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token},
    )

    assert access.status_code == 401
    assert refresh.status_code == 401


def test_registration_does_not_claim_existing_unassigned_projects(auth_client):
    session_generator = app.dependency_overrides[get_db]()
    db = next(session_generator)
    try:
        legacy_project = Project(name="Legacy unclaimed project")
        db.add(legacy_project)
        db.delete(db.query(User).filter(User.email == "owner@example.com").one())
        db.commit()
        legacy_project_id = legacy_project.id
    finally:
        session_generator.close()

    registration = _register(auth_client, email="bootstrap-user@example.com")
    assert registration.status_code == 201, registration.text

    session_generator = app.dependency_overrides[get_db]()
    db = next(session_generator)
    try:
        assert db.query(ProjectMembership).filter(
            ProjectMembership.project_id == legacy_project_id,
        ).count() == 0
    finally:
        session_generator.close()


def test_duplicate_registration_and_invalid_login_are_rejected(auth_client):
    assert _register(auth_client).status_code == 201
    duplicate = _register(auth_client)
    assert duplicate.status_code == 409

    invalid = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "new-user@example.com", "password": "wrong-password"},
    )
    unknown = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "wrong-password"},
    )
    assert invalid.status_code == unknown.status_code == 401
    assert invalid.json()["detail"] == unknown.json()["detail"]


def test_refresh_rotates_session_and_logout_revokes_access(auth_client):
    registered = _register(auth_client)
    access_before = registered.json()["access_token"]
    old_refresh = auth_client.cookies.get("contractiq_refresh")
    old_csrf = auth_client.cookies.get("contractiq_csrf")

    refreshed = auth_client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": old_csrf},
    )
    assert refreshed.status_code == 200, refreshed.text
    access_after = refreshed.json()["access_token"]
    new_refresh = auth_client.cookies.get("contractiq_refresh")
    new_csrf = auth_client.cookies.get("contractiq_csrf")
    assert new_refresh and new_refresh != old_refresh
    assert new_csrf and new_csrf != old_csrf

    invalid_csrf = auth_client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": old_csrf},
    )
    assert invalid_csrf.status_code == 403

    logout = auth_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": new_csrf},
    )
    assert logout.status_code == 204
    assert auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_after}"},
    ).status_code == 401
    assert auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_before}"},
    ).status_code == 401


def test_expired_access_token_is_rejected(auth_client):
    token = jwt.encode(
        {
            "sub": "not-a-user",
            "sid": "not-a-session",
            "type": "access",
            "iat": datetime.now(timezone.utc) - timedelta(minutes=10),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        SECRET_KEY,
        algorithm="HS256",
    )
    response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_password_reset_is_generic_single_use_and_revokes_sessions(auth_client, monkeypatch):
    import app.routes.auth as auth_routes

    assert _register(auth_client, email="reset-user@example.com").status_code == 201
    messages = []
    monkeypatch.setattr(auth_routes, "email_delivery_configured", lambda: True)
    monkeypatch.setattr(
        auth_routes,
        "send_security_email",
        lambda recipient, subject, body: messages.append((recipient, subject, body)),
    )

    request_result = auth_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "reset-user@example.com"},
    )
    assert request_result.status_code == 202
    assert request_result.json()["message"] == (
        "If an account matches that email, password reset instructions will be sent."
    )
    assert len(messages) == 1
    token = re.search(r"reset_token=([^\s&]+)", messages[0][2]).group(1)

    reset = auth_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "different-horse-battery-9"},
    )
    assert reset.status_code == 200
    assert auth_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "another-horse-battery-9"},
    ).status_code == 400
    assert auth_client.post(
        "/api/v1/auth/login",
        json={"email": "reset-user@example.com", "password": "different-horse-battery-9"},
    ).status_code == 200


def test_login_is_rate_limited(auth_client):
    responses = [
        auth_client.post(
            "/api/v1/auth/login",
            json={"email": "missing@example.com", "password": "bad-password"},
        )
        for _ in range(6)
    ]
    assert [response.status_code for response in responses[:5]] == [401] * 5
    assert responses[5].status_code == 429
