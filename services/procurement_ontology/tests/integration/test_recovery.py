"""Real TDB2 + SQLite recovery into an empty, isolated target."""

import json
import os
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from test_store import current_platform_versions, store
from procurement_ontology.identity import Credentials, IdentityStore
from procurement_ontology.models import Applicability, KnowledgeItem, SourceSpan
from procurement_ontology.query import KnowledgeQuery
from procurement_ontology.schema_catalog import SchemaCatalog


@pytest.fixture
def environment(store, tmp_path):
    from procurement_ontology.backup import BackupManager
    from procurement_ontology.governance import GovernanceService
    from procurement_ontology.intake import IntakeService

    identities = IdentityStore(tmp_path / "source/control.sqlite3", gate=store.gate)
    platform = identities.bootstrap_admin(Credentials("platform", "synthetic-platform-password"))
    identities.create_company("test_buyer1", platform)
    buyer = identities.create_account("test_buyer1", "company_admin", Credentials("buyer", "synthetic-buyer-password"), platform)
    store.provision_company("test_buyer1", current_platform_versions(store))
    identities.mark_company_ready("test_buyer1", platform)
    catalog = SchemaCatalog(identities.path, gate=store.gate)
    catalog.activate_schema(buyer, "test_buyer1", "computer", "v1")
    source = IntakeService(store).submit(buyer, "原厂上门", True)
    item = KnowledgeItem(id="warranty", kind="CollectionField", label="保修方式", category_id="test_buyer1:computer",
                         simulated=True, schema_version="v1", scope=Applicability(project_ref="P1"),
                         source_spans=[SourceSpan(revision_id=source.id, start=0, end=4, quote="原厂上门")])
    governance, query = GovernanceService(store, catalog), KnowledgeQuery(store)
    batch = governance.edit_item(buyer, {"op": "add_item", "item": item.model_dump(mode="json")}, query.versions(buyer))
    old = governance.publish(buyer, "ontology", batch.id)
    item.label = "保修服务方式"
    batch = governance.edit_item(buyer, {"op": "update_item", "item": item.model_dump(mode="json")}, query.versions(buyer))
    latest = governance.publish(buyer, "ontology", batch.id)
    return BackupManager(store, identities, catalog), buyer, source, old, latest


@pytest.fixture
def target(store, tmp_path):
    from procurement_ontology.backup import BackupManager
    from procurement_ontology.store import FusekiStore
    credentials = Path(os.getenv("FUSEKI_CREDENTIALS_FILE", str(Path(__file__).resolve().parents[4] / "deploy/fuseki/runtime/credentials.json")))
    restored = FusekiStore(store.base_url, credentials, dataset_prefix="test_restore_" + uuid.uuid4().hex[:12] + "_")
    identities = IdentityStore(tmp_path / "target/control.sqlite3", gate=restored.gate)
    manager = BackupManager(restored, identities, SchemaCatalog(identities.path, gate=restored.gate))
    yield manager
    for scope in restored.list_dataset_scopes():
        restored.session.delete(f"{restored.base_url}/$/datasets/{restored.dataset_name(scope)}", timeout=30).raise_for_status()
    restored.session.close()


def test_restore_keeps_pointer_source_history_and_audit(environment, target, tmp_path):
    manager, buyer, source, old, latest = environment
    manifest = manager.backup_service(tmp_path / "backup")
    target.restore_service(tmp_path / "backup/manifest.json")
    assert {record.scope_id for record in manifest.datasets} == {"platform", "test_buyer1"}
    assert target.store.read_source("test_buyer1", source.id) == source
    assert target.store.read_version("test_buyer1", "ontology", old.id) == old
    assert target.store.read_current("test_buyer1", "ontology") == latest
    assert target.catalog.active("test_buyer1", "computer").version == "v1"
    assert target.identities.authenticate(Credentials("buyer", "synthetic-buyer-password")) == buyer
    with sqlite3.connect(target.identities.path) as db:
        assert db.execute("SELECT actor_id FROM schema_activation_audit").fetchone()[0] == buyer.account_id
    assert KnowledgeQuery(target.store).get(buyer, "warranty")["sources"][0]["quote"] == "原厂上门"
    assert not (target.identities.path.parent / "restore.incomplete").exists()


@pytest.mark.parametrize("missing", ["sqlite", "dataset"])
def test_incomplete_backup_is_rejected(environment, target, tmp_path, missing):
    manager, *_ = environment
    manifest = manager.backup_service(tmp_path / "backup")
    record = manifest.sqlite if missing == "sqlite" else manifest.datasets[0]
    (tmp_path / "backup" / record.file).unlink()
    with pytest.raises(ValueError):
        target.restore_service(tmp_path / "backup/manifest.json")
    assert target.store.list_dataset_scopes() == []


def test_backup_blocks_new_writes_and_waits_for_inflight(environment, tmp_path, monkeypatch):
    from procurement_ontology.intake import IntakeService
    from procurement_ontology.maintenance import MaintenanceError
    manager, buyer, *_ = environment
    gate = manager.store.gate
    entered, release_writer, exporting, release_export = [threading.Event() for _ in range(4)]
    original = manager._export_dataset

    def inflight():
        with gate.writer():
            entered.set()
            assert release_writer.wait(5)
            # An already admitted operation may finish while new writers are blocked.
            IntakeService(manager.store).submit(buyer, "在途来源", True)

    def pause_export(scope):
        exporting.set()
        assert release_export.wait(5)
        return original(scope)

    monkeypatch.setattr(manager, "_export_dataset", pause_export)
    with ThreadPoolExecutor(max_workers=2) as executor:
        writer = executor.submit(inflight)
        assert entered.wait(3)
        backup = executor.submit(manager.backup_service, tmp_path / "backup")
        for _ in range(100):
            if gate.maintenance_active:
                break
            time.sleep(.01)
        assert gate.maintenance_active
        assert not exporting.is_set()
        with pytest.raises(MaintenanceError):
            IntakeService(manager.store).submit(buyer, "禁止新来源", True)
        with pytest.raises(MaintenanceError):
            manager.catalog.activate_schema(buyer, "test_buyer1", "computer", "v1")
        with pytest.raises(MaintenanceError):
            manager.identities.issue_session(buyer)
        release_writer.set()
        writer.result(timeout=5)
        assert exporting.wait(3)
        release_export.set()
        backup.result(timeout=15)
    assert not gate.maintenance_active


def test_manifest_path_escape_is_rejected(environment, target, tmp_path):
    manager, *_ = environment
    manager.backup_service(tmp_path / "backup")
    path = tmp_path / "backup/manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["sqlite"]["file"] = "../outside.sqlite3"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError):
        target.restore_service(path)
    assert target.store.list_dataset_scopes() == []


def test_interrupted_restore_leaves_target_disabled_and_source_unchanged(environment, target, tmp_path, monkeypatch):
    manager, buyer, source, old, latest = environment
    manager.backup_service(tmp_path / "backup")

    def interrupted(scope):
        raise ConnectionError("restore validation interrupted")

    monkeypatch.setattr(target, "_export_dataset", interrupted)
    with pytest.raises(ConnectionError):
        target.restore_service(tmp_path / "backup/manifest.json")
    assert (target.identities.path.parent / "restore.incomplete").is_file()
    assert manager.store.read_current("test_buyer1", "ontology") == latest
    assert manager.store.read_source("test_buyer1", source.id) == source
