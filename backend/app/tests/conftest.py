import os

os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/1")
os.environ["ENV"] = "test"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-not-for-production-use"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db, engine
from app.main import app

TEST_DATABASE_URL = os.environ["DATABASE_URL"]
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function", autouse=True)
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


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


def register_and_login(client, email, password="testpass123", full_name="Test User", role="CUSTOMER"):
    client.post("/api/auth/register", json={
        "email": email, "password": password, "full_name": full_name, "role": "CUSTOMER",
    })
    if role != "CUSTOMER":
        from app.models.models import User, UserRole
        with TestSessionLocal() as db:
            user = db.query(User).filter(User.email == email.lower()).one()
            user.role = UserRole(role)
            db.commit()
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
