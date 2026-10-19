"""Real SQLite identity tests: tenant boundaries, password storage and sessions."""

import sqlite3

import pytest


def make_store(tmp_path):
    from procurement_ontology.identity import Credentials, IdentityStore

    store = IdentityStore(tmp_path / "management.sqlite")
    platform = store.bootstrap_admin(Credentials("platform-admin", "platform-password-123"))
    store.create_company("test_buyer1", platform)
    store.create_company("test_supplier1", platform)
    buyer = store.create_account(
        "test_buyer1", "company_admin", Credentials("buyer-admin", "buyer-password-123"), platform,
    )
    store.mark_company_ready("test_buyer1", platform)
    return store, platform, buyer


def test_bootstrap_admin_is_one_time(tmp_path):
    from procurement_ontology.identity import Credentials

    store, platform, _ = make_store(tmp_path)
    assert platform.scope_id == "platform"
    with pytest.raises(ValueError):
        store.bootstrap_admin(Credentials("second-admin", "other-password-123"))


def test_identity_scope_is_server_owned(tmp_path):
    from procurement_ontology.identity import Credentials, authorize

    store, _, _ = make_store(tmp_path)
    identity = store.authenticate(Credentials("buyer-admin", "buyer-password-123"))
    assert identity.scope_id == "test_buyer1"
    authorize(identity, "test_buyer1", "read")
    with pytest.raises(PermissionError):
        authorize(identity, "test_supplier1", "read")
    with pytest.raises(PermissionError):
        authorize(identity, "platform", "write")


def test_platform_cannot_read_company_knowledge(tmp_path):
    from procurement_ontology.identity import authorize

    _, platform, _ = make_store(tmp_path)
    authorize(platform, "platform", "publish")
    for action in ("read", "write", "publish", "activate_schema"):
        with pytest.raises(PermissionError):
            authorize(platform, "test_buyer1", action)


def test_passwords_are_salted_and_not_stored_as_plaintext(tmp_path):
    from procurement_ontology.identity import Credentials

    store, _, buyer = make_store(tmp_path)
    store.create_account("test_buyer1", "reader", Credentials("reader1", "buyer-password-123"), buyer)
    with sqlite3.connect(store.path) as connection:
        hashes = [row[0] for row in connection.execute(
            "SELECT password_hash FROM accounts WHERE company_id = ?", ("test_buyer1",),
        )]
    assert len(set(hashes)) == 2
    assert b"buyer-password-123" not in store.path.read_bytes()
    with pytest.raises(PermissionError):
        store.authenticate(Credentials("buyer-admin", "incorrect-password"))


def test_session_is_company_bound_and_revocable(tmp_path):
    store, _, buyer = make_store(tmp_path)
    token = store.issue_session(buyer)
    assert token.encode() not in store.path.read_bytes()
    assert store.authenticate_token(token).scope_id == "test_buyer1"
    store.revoke_session(token)
    with pytest.raises(PermissionError):
        store.authenticate_token(token)


def test_service_token_keeps_company_scope(tmp_path):
    store, _, buyer = make_store(tmp_path)
    token = store.issue_service_token(buyer)
    assert token.encode() not in store.path.read_bytes()
    assert store.authenticate_service_token(token).scope_id == "test_buyer1"
    with pytest.raises(PermissionError):
        store.authenticate_token(token)


def test_unready_company_cannot_log_in(tmp_path):
    from procurement_ontology.identity import Credentials

    store, platform, _ = make_store(tmp_path)
    store.create_account("test_supplier1", "company_admin", Credentials("supplier", "supplier-password-123"), platform)
    with pytest.raises(PermissionError):
        store.authenticate(Credentials("supplier", "supplier-password-123"))


def test_reader_cannot_edit_own_knowledge(tmp_path):
    from procurement_ontology.identity import Credentials, authorize

    store, _, buyer = make_store(tmp_path)
    reader = store.create_account("test_buyer1", "reader", Credentials("reader", "reader-password-123"), buyer)
    authorize(reader, "test_buyer1", "read")
    with pytest.raises(PermissionError):
        authorize(reader, "test_buyer1", "write")


def test_platform_cannot_inject_account_into_ready_company(tmp_path):
    from procurement_ontology.identity import Credentials

    store, platform, _ = make_store(tmp_path)
    with pytest.raises(PermissionError):
        store.create_account("test_buyer1", "company_admin", Credentials("injected", "injected-password-123"), platform)


@pytest.mark.parametrize("company_id", ["platform", "../test_buyer1", "a/b", "a;DROP"])
def test_company_identifier_is_not_a_free_path(tmp_path, company_id):
    store, platform, _ = make_store(tmp_path)
    with pytest.raises(ValueError):
        store.create_company(company_id, platform)
