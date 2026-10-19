"""Actual API/identity/query/MCP boundary; only model IO is replaced."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from test_store import store
from procurement_ontology.identity import Credentials, IdentityStore
from procurement_ontology.schema_catalog import SchemaCatalog


@pytest.fixture
def application(store, tmp_path):
    from procurement_ontology.api import create_app
    identities = IdentityStore(tmp_path / "control.sqlite3")
    platform = identities.bootstrap_admin(Credentials("platform-admin", "synthetic-platform-password"))
    catalog = SchemaCatalog(identities.path)
    class Client:
        def complete(self, prompt, show_prompt=False):
            return json.dumps({"collection_fields": [{"local_ref": "service", "label": "保修方式", "statement": "采集服务方式",
                                                       "evidence_quote": "原厂上门", "project_ref": "PRO-IT-2026-014"}]})

    app = create_app(identities, store, catalog, draft_parent=tmp_path / "drafts", client_factory=lambda binding: Client())
    with TestClient(app, base_url="http://127.0.0.1:8002") as client:
        client.headers["Authorization"] = "Bearer " + identities.issue_session(platform)
        actors = {}
        for company in ("test_buyer1", "test_supplier1"):
            response = client.post("/v1/platform/companies", json={"company_id": company, "username": company,
                                                                  "password": "synthetic-company-password"})
            assert response.status_code == 200, response.text
            actors[company] = identities.authenticate(Credentials(company, "synthetic-company-password"))
        client.headers["Authorization"] = "Bearer " + identities.issue_session(actors["test_buyer1"])
        response = client.post("/v1/manage/schemas/activate", json={"company_id": "test_buyer1", "category_key": "computer", "version": "v1"})
        assert response.status_code == 200
        yield client, app, identities, actors, platform


def test_tenant_override_is_ignored(application):
    client, app, identities, actors, _ = application
    response = client.get("/v1/ontology/items", params={"q": "", "category_key": "computer", "company_id": "test_supplier1"})
    assert response.status_code == 200
    assert response.json()["count"] == 0
    assert response.json()["versions"] == app.state.query.versions(actors["test_buyer1"])
    response = client.post("/v1/manage/schemas/activate", json={"company_id": "test_supplier1", "category_key": "computer", "version": "v1"})
    assert response.status_code == 403
    for guessed in ("other-company-item", "urn:procurement:test_supplier1:item:cost"):
        response = client.get("/v1/ontology/items/" + guessed)
        assert response.status_code == 404
        assert "test_supplier1" not in response.text


def test_platform_cannot_read_company(application):
    client, app, identities, actors, platform = application
    client.headers["Authorization"] = "Bearer " + identities.issue_session(platform)
    assert client.get("/v1/manage/tree").status_code == 403
    assert client.get("/v1/ontology/items?category_key=computer").status_code == 403
    assert client.get("/v1/platform/tree").status_code == 200
    client.headers["Authorization"] = "Bearer " + identities.issue_session(actors["test_buyer1"])
    assert client.get("/v1/platform/tree").status_code == 403


def test_company_provision_retry(application):
    client, app, identities, actors, platform = application
    before = app.state.query.versions(actors["test_buyer1"])
    client.headers["Authorization"] = "Bearer " + identities.issue_session(platform)
    response = client.post("/v1/platform/companies", json={"company_id": "test_buyer1", "username": "injected-user", "password": "synthetic-company-password"})
    assert response.status_code == 200
    assert response.json() == {"company_id": "test_buyer1", "status": "READY"}
    assert app.state.query.versions(actors["test_buyer1"]) == before
    with pytest.raises(PermissionError):
        identities.authenticate(Credentials("injected-user", "synthetic-company-password"))


def publish_item(client):
    source = client.post("/v1/manage/sources", json={"text": "本项目要求原厂上门", "simulated": True})
    assert source.status_code == 200
    run = client.post(f"/v1/manage/sources/{source.json()['id']}/extract", json={"category_key": "computer"}).json()
    assert run["status"] == "SUCCEEDED"
    batch_id = run["batch_id"]
    candidate = client.get(f"/v1/manage/batches/{batch_id}").json()["candidates"][0]
    assert client.post(f"/v1/manage/batches/{batch_id}/reviews", json={"candidate_id": candidate["id"], "decision": "ACCEPTED"}).status_code == 200
    assert client.post(f"/v1/manage/batches/{batch_id}/publish", json={"kind": "ontology"}).status_code == 200
    return candidate["item"]["id"]


def test_mcp_api_parity(application):
    from procurement_ontology.mcp_server import current_identity
    client, app, identities, actors, _ = application
    item_id = publish_item(client)
    api = client.get("/v1/ontology/items?q=&category_key=computer").json()
    assert api["count"] == 1
    detail = client.get("/v1/ontology/items/" + item_id).json()

    async def check():
        tools = await app.state.mcp.list_tools()
        assert {tool.name for tool in tools} == {"search_ontology_items", "get_ontology_item"}
        token = current_identity.set(actors["test_buyer1"])
        try:
            result = await app.state.mcp.call_tool("search_ontology_items", {"query": "", "category_key": "computer"})
            assert result.structured_content == api
            result = await app.state.mcp.call_tool("get_ontology_item", {"item_id": item_id, "observed_version": api["versions"]})
            assert result.structured_content == detail
        finally:
            current_identity.reset(token)

    asyncio.run(check())
    assert client.post("/mcp/", json={}).status_code == 401
    service_token = identities.issue_service_token(actors["test_buyer1"])
    response = client.post("/mcp/", headers={"Authorization": "Bearer " + service_token,
                                           "Accept": "application/json, text/event-stream"},
                           json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert response.status_code == 200, response.text
    assert {tool["name"] for tool in response.json()["result"]["tools"]} == {"search_ontology_items", "get_ontology_item"}
    response = client.post("/mcp/", headers={"Authorization": "Bearer " + service_token,
                                           "Accept": "application/json, text/event-stream"},
                           json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
                               "name": "get_ontology_item", "arguments": {"item_id": item_id, "observed_version": api["versions"]}}})
    assert response.status_code == 200, response.text
    assert response.json()["result"]["structuredContent"] == detail


def test_cookie_login_csrf_and_logout(application):
    client, _, _, _, _ = application
    del client.headers["Authorization"]
    response = client.post("/v1/session", json={"username": "test_buyer1", "password": "synthetic-company-password"})
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.get("/v1/me").json()["scope_id"] == "test_buyer1"
    payload = {"text": "模拟资料", "simulated": True}
    assert client.post("/v1/manage/sources", json=payload).status_code == 403
    client.headers["X-Requested-With"] = "procurement-ontology"
    client.headers["Origin"] = "http://evil.invalid"
    assert client.post("/v1/manage/sources", json=payload).status_code == 403
    client.headers["Origin"] = "http://127.0.0.1:8002"
    assert client.post("/v1/manage/sources", json=payload).status_code == 200
    assert client.delete("/v1/session").status_code == 200
    assert client.get("/v1/me").status_code == 401
