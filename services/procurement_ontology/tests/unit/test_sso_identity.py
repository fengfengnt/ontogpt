"""SSO identities stay powerless until an atomic platform assignment."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from procurement_ontology.identity import Credentials, IdentityStore
from procurement_ontology.store import VersionConflict


@pytest.fixture
def identities(tmp_path):
    store = IdentityStore(tmp_path / "control.sqlite3")
    platform = store.bootstrap_admin(Credentials("platform", "platform-password"))
    for company in ("buyer", "supplier"):
        store.create_company(company, platform)
        store.create_account(company, "company_admin", Credentials(company, "company-password"), platform)
        store.mark_company_ready(company, platform)
    return store, platform


def test_external_subject_is_unique_and_never_merges_by_username(identities):
    store, _ = identities
    with ThreadPoolExecutor(max_workers=3) as pool:
        users = list(pool.map(lambda _: store.sso_user("https://sso.example", "opaque-sub", "buyer"), range(3)))
    assert len({u["id"] for u in users}) == 1
    assert all(u["account_id"] is None for u in users)
    other = store.sso_user("https://other.example", "opaque-sub", "buyer")
    assert other["id"] != users[0]["id"]
    assert store.authenticate(Credentials("buyer", "company-password")).scope_id == "buyer"


def test_pending_token_is_not_a_business_token(identities):
    store, _ = identities
    user = store.sso_user("https://sso.example", "user", "User")
    token = store.issue_pending_session(user["id"])
    assert store.pending_user(token)["id"] == user["id"]
    assert token.encode() not in store.path.read_bytes()
    for authenticate in (store.authenticate_token, store.authenticate_service_token):
        with pytest.raises(PermissionError):
            authenticate(token)
    with pytest.raises(VersionConflict):
        store.activate_pending(token)
    store.revoke_pending_session(token)
    with pytest.raises(PermissionError):
        store.pending_user(token)


def test_assignment_is_atomic_idempotent_and_keeps_local_injection_guard(identities):
    store, platform = identities
    user = store.sso_user("https://sso.example", "user", "buyer")
    token = store.issue_pending_session(user["id"])
    with ThreadPoolExecutor(max_workers=3) as pool:
        actors = list(pool.map(lambda _: store.assign_sso_user(user["id"], "buyer", platform), range(3)))
    assert len({a.account_id for a in actors}) == 1
    actor = actors[0]
    assert (actor.scope_id, actor.role) == ("buyer", "company_admin")
    with pytest.raises(VersionConflict):
        store.assign_sso_user(user["id"], "supplier", platform)
    with pytest.raises(PermissionError):
        store.create_account("buyer", "company_admin", Credentials("injected", "company-password"), platform)
    assert store.activate_pending(token) == actor
    with pytest.raises(PermissionError):
        store.pending_user(token)
    assert store.sso_actor(user["id"]) == actor
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT COUNT(*) FROM sso_assignment_audit").fetchone()[0] == 1
        username = db.execute("SELECT username FROM accounts WHERE account_id=?", (actor.account_id,)).fetchone()[0]
    with pytest.raises(PermissionError):
        store.authenticate(Credentials(username, "company-password"))


def test_company_admin_cannot_assign_and_unready_company_is_rejected(identities):
    store, platform = identities
    user = store.sso_user("https://sso.example", "user", "User")
    buyer = store.authenticate(Credentials("buyer", "company-password"))
    with pytest.raises(PermissionError):
        store.assign_sso_user(user["id"], "buyer", buyer)
    with pytest.raises(PermissionError):
        store.list_sso_users(buyer)
    store.create_company("pending", platform)
    for company in ("pending", "missing", "platform"):
        with pytest.raises(ValueError):
            store.assign_sso_user(user["id"], company, platform)
    assert store.list_sso_users(platform)[0]["account_id"] is None


def test_expired_pending_session_cannot_activate(identities):
    store, platform = identities
    user = store.sso_user("https://sso.example", "user", "User")
    token = store.issue_pending_session(user["id"])
    store.assign_sso_user(user["id"], "buyer", platform)
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE sso_pending_sessions SET expires_at=0")
    with pytest.raises(PermissionError):
        store.activate_pending(token)
