import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base, get_db
from app.database.models import User
from app.main import app
from app.services.authentication import get_current_user, hash_password


@pytest.fixture
def isolated_client():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    @event.listens_for(test_engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    Base.metadata.create_all(bind=test_engine)
    test_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    test_user = User(
        full_name="Test Owner",
        email="owner@example.com",
        hashed_password=hash_password("test-owner-password-123"),
        is_active=True,
        is_verified=True,
    )
    with test_session() as setup_session:
        setup_session.add(test_user)
        setup_session.commit()

    def override_get_db():
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    test_engine.dispose()


@pytest.fixture
def auth_client(isolated_client):
    overridden_user = app.dependency_overrides.pop(get_current_user, None)
    yield isolated_client
    if overridden_user is not None:
        app.dependency_overrides[get_current_user] = overridden_user
