def test_register_success(client):
    resp = client.post("/api/auth/register", json={
        "email": "alice@example.com", "password": "securepass123",
        "full_name": "Alice", "role": "CUSTOMER",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "alice@example.com"
    assert "hashed_password" not in body


def test_register_duplicate_email_rejected(client):
    payload = {"email": "bob@example.com", "password": "securepass123", "full_name": "Bob", "role": "CUSTOMER"}
    r1 = client.post("/api/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = client.post("/api/auth/register", json=payload)
    assert r2.status_code == 409


def test_register_short_password_rejected(client):
    resp = client.post("/api/auth/register", json={
        "email": "x@example.com", "password": "short", "full_name": "X", "role": "CUSTOMER",
    })
    assert resp.status_code == 422


def test_register_invalid_email_rejected(client):
    resp = client.post("/api/auth/register", json={
        "email": "not-an-email", "password": "securepass123", "full_name": "X", "role": "CUSTOMER",
    })
    assert resp.status_code == 422


def test_login_success(client):
    client.post("/api/auth/register", json={
        "email": "carol@example.com", "password": "securepass123", "full_name": "Carol", "role": "CUSTOMER",
    })
    resp = client.post("/api/auth/login", json={"email": "carol@example.com", "password": "securepass123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password_rejected(client):
    client.post("/api/auth/register", json={
        "email": "dave@example.com", "password": "securepass123", "full_name": "Dave", "role": "CUSTOMER",
    })
    resp = client.post("/api/auth/login", json={"email": "dave@example.com", "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_nonexistent_user_rejected(client):
    resp = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "whatever123"})
    assert resp.status_code == 401


def test_password_is_hashed_not_plaintext(client, db_session):
    client.post("/api/auth/register", json={
        "email": "erin@example.com", "password": "securepass123", "full_name": "Erin", "role": "CUSTOMER",
    })
    from app.models.models import User
    user = db_session.query(User).filter(User.email == "erin@example.com").first()
    assert user.hashed_password != "securepass123"
    assert user.hashed_password.startswith("$2b$")


def test_me_requires_auth(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_with_valid_token(client):
    from app.tests.conftest import register_and_login
    headers = register_and_login(client, "frank@example.com")
    resp = client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "frank@example.com"


def test_me_with_invalid_token_rejected(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
