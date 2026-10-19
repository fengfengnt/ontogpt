"""Activation commits pointer and audit together; CLI delegates authenticated HTTP."""

import copy
import json
import shutil
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from procurement_ontology.identity import Credentials, IdentityStore

ROOT = Path(__file__).resolve().parents[4]


def catalog_setup(tmp_path):
    from procurement_ontology.schema_catalog import SchemaCatalog

    identities = IdentityStore(tmp_path / "management.sqlite")
    platform = identities.bootstrap_admin(Credentials("platform", "platform-password-123"))
    identities.create_company("test_buyer1", platform)
    buyer = identities.create_account("test_buyer1", "company_admin", Credentials("buyer", "buyer-password-123"), platform)
    identities.mark_company_ready("test_buyer1", platform)
    templates = tmp_path / "templates"
    shutil.copytree(ROOT / "src/ontogpt/templates/company", templates / "company")
    v1 = templates / "company/test_buyer1/computer/v1"
    shutil.copytree(v1, v1.with_name("v2"))
    registry = yaml.safe_load((ROOT / "services/procurement_ontology/schema_registry.yaml").read_text())
    v2 = copy.deepcopy(registry["schemas"][0])
    v2["version"] = "v2"
    for field in ("yaml_path", "python_path"):
        v2[field] = v2[field].replace("/v1/", "/v2/")
    registry["schemas"].append(v2)
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(yaml.safe_dump(registry), encoding="utf-8")
    catalog = SchemaCatalog(identities.path, registry_path=registry_path, template_root=templates)
    return catalog, identities, buyer, platform


def audit_count(identities):
    with sqlite3.connect(identities.path) as db:
        return db.execute("SELECT COUNT(*) FROM schema_activation_audit").fetchone()[0]


def test_activation_is_atomic(tmp_path):
    catalog, identities, buyer, _ = catalog_setup(tmp_path)
    record = catalog.activate_schema(buyer, "test_buyer1", "computer", "v1")
    assert record.previous_version is None
    assert record.actor_id == buyer.account_id
    assert catalog.active("test_buyer1", "computer").version == "v1"
    assert audit_count(identities) == 1
    with sqlite3.connect(identities.path) as db:
        db.executescript("""
            CREATE TRIGGER fail_activation BEFORE INSERT ON schema_activation_audit
            BEGIN SELECT RAISE(ABORT, 'injected audit failure'); END;
        """)
    with pytest.raises(sqlite3.IntegrityError):
        catalog.activate_schema(buyer, "test_buyer1", "computer", "v2")
    assert catalog.active("test_buyer1", "computer").version == "v1"
    assert audit_count(identities) == 1


def test_wrong_company_and_missing_artifact_fail(tmp_path):
    catalog, identities, buyer, platform = catalog_setup(tmp_path)
    for identity, company, version, error in (
        (buyer, "test_supplier1", "v1", PermissionError),
        (platform, "test_buyer1", "v1", PermissionError),
        (buyer, "test_buyer1", "v9", ValueError),
    ):
        with pytest.raises(error):
            catalog.activate_schema(identity, company, "computer", version)
    assert audit_count(identities) == 0
    with pytest.raises(ValueError):
        catalog.active("test_buyer1", "computer")


def test_deployment_does_not_activate_and_running_binding_is_pinned(tmp_path):
    catalog, _, buyer, _ = catalog_setup(tmp_path)
    catalog.activate_schema(buyer, "test_buyer1", "computer", "v1")
    held = catalog.active("test_buyer1", "computer")
    assert held.version == "v1"  # v2 already exists in the deployed registry.
    catalog.activate_schema(buyer, "test_buyer1", "computer", "v2")
    assert held.version == "v1"
    assert catalog.active("test_buyer1", "computer").version == "v2"
    assert held.yaml_path.parent.name == "v1"


def test_changed_deployment_invalidates_active_binding(tmp_path):
    catalog, identities, buyer, _ = catalog_setup(tmp_path)
    catalog.activate_schema(buyer, "test_buyer1", "computer", "v1")
    binding = catalog.active("test_buyer1", "computer")
    binding.python_path.write_text("raise RuntimeError('unreviewed code')", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        catalog.active("test_buyer1", "computer")
    assert audit_count(identities) == 1


def test_cli_calls_service_with_authenticated_request():
    from procurement_ontology.cli import activate_schema_command

    received = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received["path"] = self.path
            received["auth"] = self.headers.get("Authorization")
            received["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            body = json.dumps({"version": "v1", "audit_id": "audit-test"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = CliRunner().invoke(activate_schema_command, ["test_buyer1", "computer", "v1", "--server-url", f"http://127.0.0.1:{server.server_port}"],
                                    env={"PROCUREMENT_ADMIN_TOKEN": "synthetic-admin-token"})
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert result.exit_code == 0, result.output
    assert received == {"path": "/v1/manage/schemas/activate", "auth": "Bearer synthetic-admin-token",
                        "body": {"company_id": "test_buyer1", "category_key": "computer", "version": "v1"}}
    assert "synthetic-admin-token" not in result.output
