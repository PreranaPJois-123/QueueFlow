"""Registration, sessions, CSRF, password change/reset and brute-force limits."""
from app.core.config import settings
from app.models.models import AuditEvent, PasswordResetToken, User, UserSession
from app.tests.conftest import auth_headers, register_and_login

PW = "securepass123"


def register(client, email, password=PW, confirm=None, **extra):
    return client.post("/api/auth/register", json={"email": email, "password": password,
                                                   "confirm_password": confirm or password,
                                                   "full_name": "Alice", **extra})


def test_register_sets_httponly_session_and_csrf_cookie(client):
    resp = register(client, "alice@example.com")
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["role"] == "CUSTOMER" and "hashed_password" not in str(body)
    assert "access_token" not in body  # no token exposed to JavaScript
    set_cookie = " ".join(resp.headers.get_list("set-cookie"))
    assert f"{settings.SESSION_COOKIE_NAME}=" in set_cookie and "HttpOnly" in set_cookie.split(
        f"{settings.CSRF_COOKIE_NAME}=")[0]
    assert "samesite=lax" in set_cookie.lower()
    assert body["csrf_token"] == resp.cookies.get(settings.CSRF_COOKIE_NAME)


def test_duplicate_email_rejected_case_insensitively(client):
    assert register(client, "bob@example.com").status_code == 201
    client.cookies.clear()
    assert register(client, "BOB@example.com").status_code == 409


def test_password_policy_and_confirmation(client):
    assert register(client, "x@example.com", "short1").status_code == 422
    assert register(client, "x@example.com", "onlyletterslong").status_code == 422
    assert register(client, "x@example.com", "password123").status_code == 422
    assert register(client, "xavier@example.com", "xavier12345").status_code == 422
    resp = register(client, "x@example.com", PW, confirm="different123")
    assert resp.status_code == 422 and "match" in str(resp.json()).lower()


def test_invalid_email_rejected(client):
    assert register(client, "not-an-email").status_code == 422


def test_unknown_fields_rejected(client):
    assert register(client, "m@example.com", is_admin=True).status_code == 422


def test_password_hashed_with_argon2id(client, db_session):
    register(client, "erin@example.com")
    user = db_session.query(User).filter_by(email="erin@example.com").one()
    assert user.hashed_password.startswith("$argon2id$") and PW not in user.hashed_password


def test_legacy_bcrypt_hash_upgraded_on_login(client, db_session):
    import bcrypt
    db_session.add(User(email="legacy@example.com", full_name="Legacy",
                        hashed_password=bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()))
    db_session.commit()
    assert client.post("/api/auth/login", json={"email": "legacy@example.com", "password": PW}).status_code == 200
    db_session.expire_all()
    assert db_session.query(User).filter_by(email="legacy@example.com").one().hashed_password.startswith("$argon2id$")


def test_login_errors_do_not_reveal_account_existence(client):
    register(client, "dave@example.com")
    client.cookies.clear()
    wrong = client.post("/api/auth/login", json={"email": "dave@example.com", "password": "wrongpass123"})
    ghost = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "wrongpass123"})
    assert wrong.status_code == ghost.status_code == 401
    assert wrong.json() == ghost.json()


def test_protected_route_requires_session(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}=forged"}).status_code == 401
    # Bearer tokens are not an authentication mechanism any more
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer anything"}).status_code == 401


def test_csrf_required_for_unsafe_requests_with_session(client):
    headers = register_and_login(client, "csrf@example.com")
    no_header = {"Cookie": headers["Cookie"]}
    assert client.patch("/api/auth/me", json={"full_name": "New"}, headers=no_header).status_code == 403
    bad = {**headers, "X-CSRF-Token": "wrong"}
    assert client.patch("/api/auth/me", json={"full_name": "New"}, headers=bad).status_code == 403
    assert client.patch("/api/auth/me", json={"full_name": "New"}, headers=headers).status_code == 200


def test_foreign_origin_rejected(client):
    resp = client.post("/api/auth/login", json={"email": "a@example.com", "password": PW},
                       headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403


def test_logout_revokes_session_server_side(client, db_session):
    headers = register_and_login(client, "out@example.com")
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401  # replaying the old cookie fails
    assert db_session.query(UserSession).filter(UserSession.revoked_at.isnot(None)).count() >= 1


def test_login_rotates_session(client):
    first = register_and_login(client, "rotate@example.com")
    second = auth_headers(client.post("/api/auth/login", json={"email": "rotate@example.com", "password": "testpass123"},
                                      headers={"Cookie": first["Cookie"]}))
    client.cookies.clear()
    assert client.get("/api/auth/me", headers=first).status_code == 401
    assert client.get("/api/auth/me", headers=second).status_code == 200


def test_expired_session_rejected(client, db_session):
    from datetime import datetime, timedelta, timezone
    headers = register_and_login(client, "exp@example.com")
    db_session.query(UserSession).update({"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)})
    db_session.commit()
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_idle_session_rejected(client, db_session):
    from datetime import datetime, timedelta, timezone
    headers = register_and_login(client, "idle@example.com")
    db_session.query(UserSession).update({"last_seen_at": datetime.now(timezone.utc) - timedelta(
        minutes=settings.SESSION_IDLE_MINUTES + 1)})
    db_session.commit()
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_password_change_revokes_other_sessions(client):
    a = register_and_login(client, "chg@example.com")
    b = auth_headers(client.post("/api/auth/login", json={"email": "chg@example.com", "password": "testpass123"}))
    client.cookies.clear()
    wrong = client.post("/api/auth/password", headers=a, json={"current_password": "nope12345678",
                        "new_password": "brandnew2024x", "confirm_password": "brandnew2024x"})
    assert wrong.status_code == 400
    ok = client.post("/api/auth/password", headers=a, json={"current_password": "testpass123",
                     "new_password": "brandnew2024x", "confirm_password": "brandnew2024x"})
    assert ok.status_code == 204
    assert client.get("/api/auth/me", headers=a).status_code == 200
    assert client.get("/api/auth/me", headers=b).status_code == 401
    assert client.post("/api/auth/login", json={"email": "chg@example.com", "password": "brandnew2024x"}).status_code == 200


def test_password_reset_flow_and_no_enumeration(client, db_session, monkeypatch):
    import app.api.auth as auth_api
    sent = []
    monkeypatch.setattr(auth_api, "send_email", lambda to, subject, body: sent.append(body) or True)
    session = register_and_login(client, "reset@example.com")
    known = client.post("/api/auth/password-reset/request", json={"email": "reset@example.com"})
    unknown = client.post("/api/auth/password-reset/request", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202 and known.json() == unknown.json()
    assert len(sent) == 1
    token = sent[0].split("token=")[1].split()[0]
    assert db_session.query(PasswordResetToken).one().token_hash != token  # only a digest is stored
    resp = client.post("/api/auth/password-reset/confirm",
                       json={"token": token, "new_password": "resetpass2024", "confirm_password": "resetpass2024"})
    assert resp.status_code == 200
    assert client.get("/api/auth/me", headers=session).status_code == 401  # all sessions revoked
    reused = client.post("/api/auth/password-reset/confirm",
                         json={"token": token, "new_password": "another2024xx", "confirm_password": "another2024xx"})
    assert reused.status_code == 400
    assert client.post("/api/auth/login", json={"email": "reset@example.com", "password": "resetpass2024"}).status_code == 200


def test_login_brute_force_lockout(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_PER_MINUTE", 1000)
    register(client, "victim@example.com")
    client.cookies.clear()
    codes = [client.post("/api/auth/login", json={"email": "victim@example.com", "password": "wrongpass999"}).status_code
             for _ in range(settings.LOGIN_MAX_FAILURES)]
    assert codes == [401] * settings.LOGIN_MAX_FAILURES
    # Even the correct password is refused while locked out.
    assert client.post("/api/auth/login", json={"email": "victim@example.com", "password": PW}).status_code == 429


def test_auth_route_rate_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_PER_MINUTE", 3)
    codes = [client.post("/api/auth/login", json={"email": f"n{i}@example.com", "password": PW}).status_code
             for i in range(5)]
    assert codes[:3] == [401, 401, 401] and 429 in codes[3:]


def test_security_events_audited(client, db_session):
    register_and_login(client, "audit@example.com")
    client.post("/api/auth/login", json={"email": "audit@example.com", "password": "badpassword1"})
    actions = {a for (a,) in db_session.query(AuditEvent.action).all()}
    assert {"auth.register", "auth.login", "auth.login_failed"} <= actions


def test_security_headers_present(client):
    resp = client.get("/api/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"


def test_oversized_body_rejected(client):
    resp = client.post("/api/auth/login", content=b"x" * (settings.MAX_REQUEST_BYTES + 1),
                       headers={"Content-Type": "application/json"})
    assert resp.status_code == 413
