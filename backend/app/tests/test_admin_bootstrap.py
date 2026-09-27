import pytest

from app.models.models import User, UserRole
from app.provision_user import bootstrap_admin_from_env


def test_first_admin_provisioned_once(monkeypatch, db_session):
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "operator@example.com")
    monkeypatch.setenv("INITIAL_ADMIN_NAME", "Operator")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "strong-password-for-first-admin")
    bootstrap_admin_from_env()
    bootstrap_admin_from_env()
    users = db_session.query(User).all()
    assert len(users) == 1
    assert users[0].role == UserRole.ADMIN
    assert users[0].hashed_password != "strong-password-for-first-admin"


def test_bootstrap_rejects_partial_config(monkeypatch):
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "operator@example.com")
    monkeypatch.delenv("INITIAL_ADMIN_NAME", raising=False)
    monkeypatch.delenv("INITIAL_ADMIN_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="Set all INITIAL_ADMIN"):
        bootstrap_admin_from_env()


def test_bootstrap_does_not_promote_customer(monkeypatch, db_session):
    db_session.add(User(email="owner@example.com", full_name="Owner",
                        hashed_password="existing", role=UserRole.CUSTOMER))
    db_session.commit()
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "owner@example.com")
    monkeypatch.setenv("INITIAL_ADMIN_NAME", "Owner")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "strong-password-for-first-admin")
    with pytest.raises(ValueError, match="existing account"):
        bootstrap_admin_from_env()
    assert db_session.query(User).one().role == UserRole.CUSTOMER
