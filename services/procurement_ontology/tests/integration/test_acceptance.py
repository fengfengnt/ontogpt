"""Opt-in paid-provider acceptance against this project's local running service.

No default test run invokes a paid model. Credentials remain in an ignored local file.
"""

import hashlib
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import requests

ROOT = Path(__file__).resolve().parents[4]
BASE = os.getenv("PROCUREMENT_LIVE_ACCEPTANCE_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not BASE, reason="Explicit PROCUREMENT_LIVE_ACCEPTANCE_URL required for paid-provider acceptance")


def _profiles():
    return json.loads(Path(os.environ["PROCUREMENT_LIVE_CREDENTIALS_FILE"]).read_text(encoding="utf-8"))


def _login(role):
    session = requests.Session()
    session.trust_env = False
    session.headers["X-Requested-With"] = "procurement-ontology"
    response = session.post(BASE + "/v1/session", json=_profiles()[role], timeout=20)
    if response.status_code != 200:
        raise AssertionError(f"Local {role} login failed, HTTP {response.status_code}")
    return session


def _request(session, method, path, body=None):
    response = session.request(method, BASE + path, json=body, timeout=300)
    if response.status_code >= 400:
        raise AssertionError(f"{method} {path}: HTTP {response.status_code}; code={response.json().get('code')}")
    return response.json()


def _provision(platform, company):
    credentials = _profiles()[company]
    response = platform.post(BASE + "/v1/platform/companies", json={"company_id": company, **credentials}, timeout=30)
    if response.status_code != 200:
        raise AssertionError(f"Local {company} provisioning failed, HTTP {response.status_code}")


def _activate(session, company):
    active = session.get(BASE + "/v1/manage/schemas/active?category_key=computer", timeout=20)
    if active.status_code == 200:
        return active.json()
    token_path = Path(os.environ["PROCUREMENT_LIVE_CREDENTIALS_FILE"]).parent / (company + ".session.token")
    token_path.write_text(session.cookies.get("procurement_session"), encoding="utf-8")
    result = subprocess.run(["uv", "run", "--project", "services/procurement_ontology", "activate-schema", company, "computer", "v1",
                             "--server-url", BASE, "--token-file", str(token_path)], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, "Authenticated activation command failed"
    return _request(session, "GET", "/v1/manage/schemas/active?category_key=computer")


def test_buyer_supplier_end_to_end():
    parsed = urlsplit(BASE)
    assert parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}, "Live acceptance is local only"
    platform = _login("platform")
    for company in ("test_buyer1", "test_supplier1"):
        _provision(platform, company)
    buyer, supplier = _login("test_buyer1"), _login("test_supplier1")
    report, chosen = {"review_mode": "自动化技术验收中的模拟人工审核；不是业务专家正式验收", "runs": {}}, {}
    try:
        for company, session, fixture, required_kind in (
            ("test_buyer1", buyer, ROOT / "tests/fixtures/procurement/laptop-purchase-case.md", "CollectionField"),
            ("test_supplier1", supplier, ROOT / "services/procurement_ontology/tests/fixtures/supplier-laptop-bid-case.md", "InternalCost"),
        ):
            active = _activate(session, company)
            text = fixture.read_bytes().decode("utf-8")
            digest = hashlib.sha256(text.encode()).hexdigest()
            sources = _request(session, "GET", "/v1/manage/sources")
            source = next((source for source in sources if source["sha256"] == digest), None)
            if source is None:
                source = _request(session, "POST", "/v1/manage/sources", {"text": text, "simulated": True})
            assert source["sha256"] == digest and source["simulated"] is True
            run = _request(session, "POST", f"/v1/manage/sources/{source['id']}/extract", {"category_key": "computer"})
            assert run["status"] == "SUCCEEDED", f"Actual model run failed: {run['error_code']}"
            assert run["model_id"] == "deepseek/deepseek-flash"
            assert (run["yaml_sha256"], run["python_sha256"]) == (active["yaml_sha256"], active["python_sha256"])
            result = _request(session, "GET", "/v1/manage/batches/" + run["batch_id"])
            candidates = result["candidates"]
            assert candidates
            eligible = []
            kinds = {}
            for candidate in candidates:
                item = candidate["item"]
                kind = item.get("kind", "relation")
                kinds[kind] = kinds.get(kind, 0) + 1
                for span in item["source_spans"]:
                    assert span["quote"] == text[span["start"]:span["end"]]
                if kind == required_kind and item["source_spans"] and candidate["status"] != "MODEL_SUGGESTION":
                    if company == "test_supplier1" and "迁移" in item["label"] + json.dumps(item["properties"], ensure_ascii=False):
                        continue
                    eligible.append(candidate)
            assert eligible, f"No anchored {required_kind} candidate available for simulated review"
            selected = next((candidate for candidate in eligible if "保修" in candidate["item"]["label"]), eligible[0])
            chosen[company] = selected["item"]["id"]
            if result["batch"] is None or result["batch"]["status"] != "PUBLISHED":
                assert not _request(session, "GET", "/v1/ontology/items?category_key=computer")["items"], "Candidates must not be queryable before publication"
                for candidate in candidates:
                    body = {"candidate_id": candidate["id"], "decision": "ACCEPTED" if candidate["id"] == selected["id"] else "REJECTED"}
                    if candidate["id"] == selected["id"] and not candidate["item"]["scope"].get("project_ref"):
                        project = "PRO-IT-2026-014" if company == "test_buyer1" else "BID-IT-2026-014"
                        assert project in text
                        corrected = {**candidate["item"], "scope": {**candidate["item"]["scope"], "project_ref": project}}
                        body["corrected"] = corrected
                    _request(session, "POST", f"/v1/manage/batches/{run['batch_id']}/reviews", body)
                _request(session, "POST", f"/v1/manage/batches/{run['batch_id']}/publish", {"kind": "ontology"})
            detail = _request(session, "GET", "/v1/ontology/items/" + selected["item"]["id"])
            assert detail["item"]["simulated"] is True and detail["item"]["scope"]["project_ref"]
            report["runs"][company] = {"id": run["id"], "model_id": run["model_id"], "schema_version": run["schema_version"],
                "source_sha256": digest, "candidate_count": len(candidates), "kinds": kinds,
                "anchored_count": sum(bool(candidate["item"]["source_spans"]) for candidate in candidates),
                "published_item_id": selected["item"]["id"], "versions": detail["versions"]}

        assert buyer.get(BASE + "/v1/ontology/items/" + chosen["test_supplier1"], timeout=20).status_code == 404
        assert supplier.get(BASE + "/v1/ontology/items/" + chosen["test_buyer1"], timeout=20).status_code == 404
        assert platform.get(BASE + "/v1/ontology/items?category_key=computer", timeout=20).status_code == 403
        assert supplier.post(BASE + "/v1/agent/questions", json={"question": "查询甲方成本"}, timeout=20).status_code == 403
        buyer_item = _request(buyer, "GET", "/v1/ontology/items/" + chosen["test_buyer1"])
        answer = _request(buyer, "POST", "/v1/agent/questions", {"question": buyer_item["item"]["label"]})
        assert answer["citations"] and answer["versions"] == buyer_item["versions"]
        assert all(citation["item_id"] == chosen["test_buyer1"] for citation in answer["citations"])
        report["agent"] = {"versions": answer["versions"], "citation_ids": [citation["item_id"] for citation in answer["citations"]]}
        report["cross_company_guessed_id_status"] = 404
        report["platform_company_read_status"] = 403
        report["supplier_buyer_agent_status"] = 403
        path = Path(os.environ["PROCUREMENT_LIVE_CREDENTIALS_FILE"]).parent / "live-acceptance-evidence.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        for session in (platform, buyer, supplier):
            session.close()
