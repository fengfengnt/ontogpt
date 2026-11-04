"""HTTP acceptance for pending identities, password fallback and assignment."""

from urllib.parse import parse_qs, urlparse
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from test_sso import oidc
from procurement_ontology.api import create_app
from procurement_ontology.identity import Credentials, IdentityStore
from procurement_ontology.maintenance import WriteGate
from procurement_ontology.schema_catalog import SchemaCatalog


@pytest.fixture
def application(tmp_path):
    identities = IdentityStore(tmp_path / "control.sqlite3")
    platform = identities.bootstrap_admin(Credentials("platform-admin", "synthetic-platform-password"))
    actors = {}
    for company in ("test_buyer1", "test_supplier1"):
        identities.create_company(company, platform)
        actors[company] = identities.create_account(company, "company_admin", Credentials(company, "synthetic-company-password"), platform)
        identities.mark_company_ready(company, platform)
    # These tests exercise authentication before knowledge IO; no RDF server is contacted.
    store = SimpleNamespace(gate=WriteGate(), list_runs=lambda company: [])
    app = create_app(identities, store, SchemaCatalog(identities.path), draft_parent=tmp_path / "drafts")
    client = TestClient(app, base_url="http://127.0.0.1:8002")
    client.headers["Authorization"] = "Bearer " + identities.issue_session(actors["test_buyer1"])
    yield client, app, identities, actors, platform
    client.close()


def browser_for(application, oidc):
    from procurement_ontology.sso import SSOClient
    _, app, identities, _, _ = application
    protocol, _, _ = oidc
    app.state.sso = SSOClient(protocol.config, identities, http_client=protocol.http)
    return TestClient(app, base_url="https://ontology.example", follow_redirects=False)


def login_sso(browser, oidc):
    _, _, data = oidc
    start = browser.get("/v1/auth/sso/start")
    assert start.status_code == 303
    data["authorize"] = parse_qs(urlparse(start.headers["location"]).query)
    cookie = start.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie
    state = data["authorize"]["state"][0]
    result = browser.get("/v1/auth/sso/callback", params={"code": "valid-code", "state": state})
    assert result.status_code == 303, result.text
    assert result.headers["location"] == "/"
    assert "no-store" in result.headers["cache-control"]
    return result


def test_unconfigured_sso_keeps_local_password_login(application):
    _, app, _, _, _ = application
    with TestClient(app, base_url="https://ontology.example") as browser:
        assert browser.get("/v1/auth/sso/config").json() == {"enabled": False}
        assert browser.get("/v1/auth/sso/start").status_code == 503
        response = browser.post("/v1/session", json={"username": "test_buyer1", "password": "synthetic-company-password"})
        assert response.status_code == 200
        assert response.json()["role"] == "company_admin"
        assert "Secure" in response.headers["set-cookie"]


def test_pending_login_assignment_activation_and_logout(application, oidc):
    client, app, identities, actors, platform = application
    browser = browser_for(application, oidc)
    login_sso(browser, oidc)
    pending = browser.get("/v1/me").json()
    assert pending["status"] == "PENDING_ASSIGNMENT"
    assert pending["scope_id"] is None and pending["role"] is None
    for path in ("/v1/manage/tree", "/v1/platform/tree", "/v1/ontology/items", "/v1/platform/sso-users"):
        assert browser.get(path).status_code == 401
    headers = {"X-Requested-With": "procurement-ontology"}
    assert browser.post("/v1/manage/service-token", headers=headers).status_code == 401
    assert browser.post("/mcp/", json={}).status_code == 401
    assert browser.post("/v1/session/activate").status_code == 403
    assert browser.post("/v1/session/activate", headers={**headers, "Origin": "https://evil.example"}).status_code == 403
    assert browser.post("/v1/session/activate", headers=headers).status_code == 409
    client.headers["Authorization"] = "Bearer " + identities.issue_session(platform)
    user = client.get("/v1/platform/sso-users").json()[0]
    assert client.get("/v1/platform/companies").json() == ["test_buyer1", "test_supplier1"]
    assignment = f"/v1/platform/sso-users/{user['id']}/assignment"
    assert client.post(assignment, json={"company_id": "test_buyer1", "role": "platform_admin"}).status_code == 422
    assert client.post(assignment, json={"company_id": "test_buyer1"}).status_code == 200
    assert browser.get("/v1/manage/tree").status_code == 401
    assert browser.post("/v1/session/activate", headers=headers).status_code == 200
    actor = browser.get("/v1/me").json()
    assert (actor["scope_id"], actor["role"]) == ("test_buyer1", "company_admin")
    assert browser.post("/v1/manage/service-token", headers=headers).status_code == 200
    assert browser.get("/v1/platform/tree").status_code == 403
    assert browser.delete("/v1/session", headers=headers).status_code == 200
    assert browser.get("/v1/me").status_code == 401
    login_sso(browser, oidc)
    assert browser.get("/v1/me").json()["scope_id"] == "test_buyer1"


def test_company_admin_cannot_list_or_assign_sso_users(application):
    client, app, identities, _, _ = application
    user = identities.sso_user("https://sso.example", "new", "New user")
    assert client.get("/v1/platform/sso-users").status_code == 403
    assert client.get("/v1/platform/companies").status_code == 403
    assert client.post(f"/v1/platform/sso-users/{user['id']}/assignment", json={"company_id": "test_buyer1"}).status_code == 403


def test_pending_can_log_out_or_use_password_without_merging(application, oidc):
    browser = browser_for(application, oidc)
    headers = {"X-Requested-With": "procurement-ontology"}
    login_sso(browser, oidc)
    assert browser.delete("/v1/session", headers=headers).status_code == 200
    assert browser.get("/v1/me").status_code == 401
    login_sso(browser, oidc)
    assert browser.post("/v1/session", headers=headers, json={"username": "platform-admin", "password": "synthetic-platform-password"}).status_code == 200
    assert browser.get("/v1/me").json()["role"] == "platform_admin"
    assert "procurement_pending" not in browser.cookies
    assert len(application[2].list_sso_users(application[4])) == 1


def test_callback_rejects_duplicate_parameters_and_foreign_browser(application, oidc):
    browser = browser_for(application, oidc)
    _, _, data = oidc
    start = browser.get("/v1/auth/sso/start")
    data["authorize"] = parse_qs(urlparse(start.headers["location"]).query)
    state = data["authorize"]["state"][0]
    foreign = TestClient(application[1], base_url="https://ontology.example", follow_redirects=False)
    assert foreign.get("/v1/auth/sso/callback", params={"state": state, "code": "valid-code"}).status_code == 400
    assert browser.get("/v1/auth/sso/callback", params=[("state", state), ("state", state), ("code", "valid-code")]).status_code == 400
    assert browser.get("/v1/me").status_code == 401
    assert not application[2].list_sso_users(application[4])


def test_password_path_is_served_directly_without_api_fallback(application, tmp_path):
    from procurement_ontology.api import create_app
    _, app, identities, _, _ = application
    dist = tmp_path / "frontend"
    dist.mkdir()
    (dist / "index.html").write_text("<html>工作台</html>", encoding="utf-8")
    routed = create_app(identities, app.state.store, app.state.catalog, draft_parent=tmp_path / "drafts", frontend_dist=dist)
    browser = TestClient(routed)
    assert "工作台" in browser.get("/login/password").text
    assert browser.get("/v1/unknown").status_code == 404
