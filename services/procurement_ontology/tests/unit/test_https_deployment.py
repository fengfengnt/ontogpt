import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from test_api_mcp import application, store
from procurement_ontology.api import create_app


def https_app(application, tmp_path):
    _, app, identities, _, _ = application
    return create_app(identities, app.state.store, app.state.catalog,
                      draft_parent=tmp_path / "drafts", public_origin="https://ontology.lvh.me")


def test_https_login_cookie_origin_and_logout(application, tmp_path):
    app = https_app(application, tmp_path)
    with TestClient(app, base_url="https://ontology.lvh.me") as client:
        response = client.post("/v1/session", json={"username": "test_buyer1", "password": "synthetic-company-password"})
        assert response.status_code == 200
        assert "; Secure" in response.headers["set-cookie"]
        assert "HttpOnly" in response.headers["set-cookie"]
        headers = {"Origin": "https://evil.invalid", "X-Requested-With": "procurement-ontology"}
        assert client.post("/v1/manage/sources", json={"text": "测试", "simulated": True}, headers=headers).status_code == 403
        headers["Origin"] = "https://ontology.lvh.me"
        response = client.delete("/v1/session", headers=headers)
        assert response.status_code == 200
        assert "; Secure" in response.headers["set-cookie"]
        assert client.get("/health", headers={"Host": "evil.invalid"}).status_code == 400


def test_mcp_accepts_configured_https_origin(application, tmp_path):
    app = https_app(application, tmp_path)
    from procurement_ontology.identity import Credentials
    actor = app.state.identities.authenticate(Credentials("test_buyer1", "synthetic-company-password"))
    token = app.state.identities.issue_service_token(actor)
    with TestClient(app, base_url="https://ontology.lvh.me") as client:
        headers = {"Authorization": "Bearer " + token, "Origin": "https://ontology.lvh.me", "Accept": "application/json, text/event-stream"}
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        assert client.post("/mcp/", json=payload, headers=headers).status_code == 200
        headers["Origin"] = "https://evil.invalid"
        assert client.post("/mcp/", json=payload, headers=headers).status_code == 403


@pytest.mark.parametrize("peer,expected", [("172.30.0.1", 401), ("198.51.100.10", 403)])
def test_forwarded_scheme_requires_trusted_peer(application, tmp_path, peer, expected):
    app = ProxyHeadersMiddleware(https_app(application, tmp_path), trusted_hosts="172.30.0.1")
    with TestClient(app, base_url="http://ontology.lvh.me", client=(peer, 12345)) as client:
        response = client.post("/v1/session", headers={"Origin": "https://ontology.lvh.me", "X-Forwarded-Proto": "https"},
                               json={"username": "nonexistent", "password": "synthetic-not-a-password"})
        assert response.status_code == expected


@pytest.mark.parametrize("origin", ["https://*.lvh.me", "https://user:pass@ontology.lvh.me", "https://ontology.lvh.me/path"])
def test_public_origin_rejects_unsafe_configuration(application, tmp_path, origin):
    _, app, identities, _, _ = application
    with pytest.raises(ValueError):
        create_app(identities, app.state.store, app.state.catalog, draft_parent=tmp_path, public_origin=origin)


def test_serve_uses_explicit_proxy_addresses_and_rejects_network_trust(tmp_path, monkeypatch):
    from click.testing import CliRunner
    from procurement_ontology import runtime
    import uvicorn
    monkeypatch.setenv("PROCUREMENT_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("PROCUREMENT_BIND_HOST", "0.0.0.0")
    monkeypatch.setenv("PROCUREMENT_TRUSTED_PROXIES", "172.30.0.1")
    monkeypatch.setattr(runtime, "build_app", lambda path: "synthetic-app")
    observed = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: observed.update(kwargs))
    assert CliRunner().invoke(runtime.main, ["serve"]).exit_code == 0
    assert observed["host"] == "0.0.0.0" and observed["workers"] == 1
    assert observed["forwarded_allow_ips"] == ["172.30.0.1"]
    for unsafe in ("*", "172.30.0.0/16"):
        monkeypatch.setenv("PROCUREMENT_TRUSTED_PROXIES", unsafe)
        assert CliRunner().invoke(runtime.main, ["serve"]).exit_code != 0
