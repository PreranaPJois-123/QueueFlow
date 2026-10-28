"""Test fixtures. The suite runs against a real, disposable PostgreSQL
database (pgvector + btree_gist) so locking, constraints and vector search are
exercised for real. Set TEST_DATABASE_URL; every table in it is truncated."""
import os

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise SystemExit("Set TEST_DATABASE_URL to a disposable PostgreSQL database (all its tables are reset).")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/1")
os.environ["ENV"] = "test"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-not-for-production-use-0123456789"
os.environ["REALTIME_BACKEND"] = "local"
os.environ["CORS_ORIGINS"] = "http://testserver,http://localhost:8080,http://localhost:5173"
os.environ.pop("LLM_PROVIDER", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import Base, engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import models as _models  # noqa: E402,F401

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
DEFAULT_PASSWORD = "testpass123"


@pytest.fixture(scope="session", autouse=True)
def schema():
    with engine.begin() as conn:
        for ext in ("vector", "btree_gist"):
            conn.execute(text(f"CREATE EXTENSION IF NOT EXISTS {ext}"))
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def clean_tables(schema):
    yield
    names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    from app.core import rate_limit
    from app.core.redis_client import redis_client
    rate_limit._local.clear()
    try:
        redis_client.flushdb()  # TEST_REDIS_URL database only (db 1 by default)
    except Exception:
        pass


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    db = TestSessionLocal()
    yield db
    db.close()


def auth_headers(response) -> dict:
    """Turn a login/register response into explicit per-user request headers
    (session cookie + CSRF header), so one TestClient can act as many users."""
    session = response.cookies.get(settings.SESSION_COOKIE_NAME)
    csrf = response.cookies.get(settings.CSRF_COOKIE_NAME)
    assert session and csrf, response.text
    return {"Cookie": f"{settings.SESSION_COOKIE_NAME}={session}; {settings.CSRF_COOKIE_NAME}={csrf}",
            "X-CSRF-Token": csrf}


def register_and_login(client, email, password=DEFAULT_PASSWORD, full_name="Test User", role="CUSTOMER"):
    client.post("/api/auth/register", json={"email": email, "password": password, "confirm_password": password,
                                            "full_name": full_name})
    if role != "CUSTOMER":
        from app.models.models import User, UserRole
        with TestSessionLocal() as db:
            user = db.query(User).filter(User.email == email.lower()).one()
            user.role = UserRole(role)
            db.commit()
    client.cookies.clear()
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    client.cookies.clear()
    return auth_headers(response)
