import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.database import Base, get_db

# ── In-memory SQLite test database ───────────────────────────────────────────
# Zero setup required — exists only during test run
TEST_DATABASE_URL = "sqlite:///./test_temp.db"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)


# ── Create all tables once per test session ───────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


# ── DB session per test — rolls back after each test ─────────────────────────
@pytest.fixture(scope="function")
def db():
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# ── Test client wired to test DB ─────────────────────────────────────────────
@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Regular user fixture ──────────────────────────────────────────────────────
@pytest.fixture(scope="function")
def user_token(client):
    client.post("/users/", json={
        "email": "testuser@example.com",
        "password": "testpassword123"
    })
    response = client.post("/auth/login", json={
        "email": "testuser@example.com",
        "password": "testpassword123"
    })
    return response.json()["access_token"]


# ── Admin user fixture ────────────────────────────────────────────────────────
@pytest.fixture(scope="function")
def admin_token(client, db):
    from app.models.user import User
    from app.services.auth_service import hash_password
    from app.services.settings_service import SettingsService

    admin = User(
        email="admin@example.com",
        password=hash_password("adminpassword123"),
        role="admin",
        is_active=True
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    SettingsService.create_default_settings(db, admin.id)

    response = client.post("/auth/login", json={
        "email": "admin@example.com",
        "password": "adminpassword123"
    })
    return response.json()["access_token"]