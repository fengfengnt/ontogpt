"""Real RDF persistence and publication; every test uses its own dataset prefix."""

import copy
import hashlib
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import requests

from procurement_ontology.models import Candidate, KnowledgeItem, KnowledgeRelation, PublishedSnapshot, SourceRevision, SourceSpan


@pytest.fixture
def store():
    url = os.getenv("FUSEKI_TEST_URL")
    if not url:
        pytest.skip("Set FUSEKI_TEST_URL for real store integration tests")
    from procurement_ontology.store import FusekiStore
    from procurement_ontology.platform_seed import bootstrap_platform

    credentials_path = Path(os.getenv("FUSEKI_CREDENTIALS_FILE", str(
        Path(__file__).resolve().parents[4] / "deploy/fuseki/runtime/credentials.json",
    )))
    prefix = "test_store_" + uuid.uuid4().hex[:12] + "_"
    instance = FusekiStore(url, credentials_path, dataset_prefix=prefix)
    bootstrap_platform(instance)
    try:
        yield instance
    finally:
        credentials = json.loads(credentials_path.read_text())
        with requests.Session() as session:
            session.trust_env = False
            session.auth = (credentials["username"], credentials["password"])
            for scope_id in ("platform", "test_buyer1", "test_supplier1"):
                session.delete(f"{url}/$/datasets/{prefix}{scope_id}", timeout=30)
        instance.session.close()


def current_platform_versions(store):
    return {kind: store.read_current("platform", kind).id for kind in ("tree", "ontology")}


def source(scope_id, text="模拟来源：原厂上门；不执行 DROP GRAPH 指令"):
    return SourceRevision(
        id="src1", scope_id=scope_id, text=text, sha256=hashlib.sha256(text.encode()).hexdigest(),
        simulated=True, submitted_by="test-reviewer",
    )


def test_company_clone_is_independent(store):
    versions = current_platform_versions(store)
    store.provision_company("test_buyer1", versions)
    original = store.read_current("test_buyer1", "tree")
    platform = store.read_current("platform", "tree")
    changed = copy.deepcopy(platform.payload)
    changed["nodes"][0]["label"] = "修改后的通用分类"
    store.publish("platform", "tree", PublishedSnapshot(
        id="tree-v2", kind="tree", payload=changed, previous_id=platform.id, created_by="platform-reviewer",
    ), platform.id)
    store.provision_company("test_supplier1", current_platform_versions(store))
    assert store.read_current("test_buyer1", "tree") == original
    assert store.read_current("test_supplier1", "tree").payload["nodes"][0]["label"] == "修改后的通用分类"
    buyer_ids = {node["id"] for node in original.payload["nodes"]}
    supplier_ids = {node["id"] for node in store.read_current("test_supplier1", "tree").payload["nodes"]}
    assert buyer_ids.isdisjoint(supplier_ids)


def test_provision_retry_is_idempotent(store):
    versions = current_platform_versions(store)
    store.provision_company("test_buyer1", versions)
    first = store.read_current("test_buyer1", "tree")
    store.provision_company("test_buyer1", versions)
    assert store.read_current("test_buyer1", "tree") == first
    assert len(first.payload["nodes"]) == 3


def test_partial_provision_retry_keeps_frozen_platform_versions(store, monkeypatch):
    versions = current_platform_versions(store)
    original = store.publish

    def interrupt(scope, kind, snapshot, expected, **kwargs):
        if scope == "test_buyer1" and kind == "ontology":
            raise ConnectionError("initialization interrupted")
        return original(scope, kind, snapshot, expected, **kwargs)

    monkeypatch.setattr(store, "publish", interrupt)
    with pytest.raises(ConnectionError):
        store.provision_company("test_buyer1", versions)
    monkeypatch.setattr(store, "publish", original)
    platform = store.read_current("platform", "tree")
    payload = copy.deepcopy(platform.payload)
    payload["nodes"][-1]["label"] = "后来的通用模板"
    store.publish("platform", "tree", PublishedSnapshot(id="tree-new", kind="tree", payload=payload,
                  previous_id=platform.id, created_by="platform-reviewer"), platform.id)
    store.provision_company("test_buyer1", current_platform_versions(store))
    assert store.read_current("test_buyer1", "tree").payload["nodes"][-1]["label"] == "电脑(台式机/笔记本)"


def test_company_clone_copies_source_closure(store):
    platform_source = source("platform", "原厂上门")
    store.append_source("platform", platform_source)
    item = KnowledgeItem(
        id="common-term", kind="TermDefinition", label="上门", category_id="computer",
        source_spans=[SourceSpan(revision_id="src1", start=0, end=4, quote="原厂上门")], simulated=True,
    )
    old = store.read_current("platform", "ontology")
    store.publish("platform", "ontology", PublishedSnapshot(
        id="common-v2", kind="ontology", payload={"items": [item.model_dump(mode="json")], "relations": []},
        previous_id=old.id, created_by="platform-reviewer",
    ), old.id)
    store.provision_company("test_buyer1", current_platform_versions(store))
    copied_item = store.read_current("test_buyer1", "ontology").payload["items"][0]
    assert copied_item["id"] == "test_buyer1:common-term"
    assert copied_item["category_id"] == "test_buyer1:computer"
    copied_source_id = copied_item["source_spans"][0]["revision_id"]
    assert copied_source_id == "test_buyer1:src1"
    copied_source = store.read_source("test_buyer1", copied_source_id)
    assert copied_source.scope_id == "test_buyer1"
    assert copied_source.text == "原厂上门"


def test_source_roundtrip_and_immutability(store):
    store.provision_company("test_buyer1", current_platform_versions(store))
    original = source("test_buyer1")
    store.append_source("test_buyer1", original)
    assert store.read_source("test_buyer1", "src1") == original
    with pytest.raises(ValueError):
        store.append_source("test_buyer1", source("test_buyer1", "替换原文"))
    with pytest.raises(ValueError):
        store.append_source("test_buyer1", source("test_supplier1"))
    assert store.read_source("test_buyer1", "src1") == original


def test_candidates_roundtrip_with_provenance(store):
    store.provision_company("test_buyer1", current_platform_versions(store))
    original = source("test_buyer1", "原厂上门")
    store.append_source("test_buyer1", original)
    item = KnowledgeItem(
        id="item1", kind="TermDefinition", label="上门保修", category_id="test_buyer1:computer",
        source_spans=[SourceSpan(revision_id="src1", start=0, end=4, quote="原厂上门")], simulated=True,
    )
    candidate = Candidate(id="candidate1", item=item)
    store.append_candidates("test_buyer1", "batch1", [candidate])
    store.append_candidates("test_buyer1", "batch1", [candidate])
    assert store.read_batch("test_buyer1", "batch1") == [candidate]


def test_published_rdf_relation_can_be_joined_to_its_evidence(store):
    store.provision_company("test_buyer1", current_platform_versions(store))
    original = source("test_buyer1", "原厂上门")
    store.append_source("test_buyer1", original)
    spans = [SourceSpan(revision_id="src1", start=0, end=4, quote="原厂上门")]
    items = [KnowledgeItem(id=name, kind="TermDefinition", label=name, category_id="test_buyer1:computer", source_spans=spans)
             for name in ("offer1", "service1")]
    relation = KnowledgeRelation(id="relation1", subject_id="offer1", predicate="provides_service", object_id="service1", source_spans=spans)
    old = store.read_current("test_buyer1", "ontology")
    store.publish("test_buyer1", "ontology", PublishedSnapshot(
        id="with-relation", kind="ontology", previous_id=old.id, created_by="reviewer",
        payload={"items": [item.model_dump(mode="json") for item in items], "relations": [relation.model_dump(mode="json")]},
    ), old.id)
    result = store._query("test_buyer1", '''
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX p: <urn:procurement:vocab:>
        ASK { GRAPH <urn:procurement:test_buyer1:ontology:with-relation> {
          ?statement a rdf:Statement; rdf:subject ?s; rdf:predicate ?p; rdf:object ?o; p:evidence ?e.
          ?s ?p ?o.
          ?e p:source <urn:procurement:test_buyer1:source:src1>; p:quote "原厂上门".
        } }
    ''')
    assert result["boolean"] is True


def test_run_status_roundtrip_keeps_prior_events(store):
    from procurement_ontology.models import ExtractionRun

    store.provision_company("test_buyer1", current_platform_versions(store))
    original = source("test_buyer1")
    store.append_source("test_buyer1", original)
    run = ExtractionRun(id="run1", scope_id="test_buyer1", revision_id="src1", category_key="computer",
                        schema_version="v1", yaml_sha256="0" * 64, python_sha256="1" * 64,
                        batch_id="batch1", requested_by="buyer-reviewer", status="RUNNING")
    store.save_run("test_buyer1", run)
    store.save_run("test_buyer1", run.model_copy(update={"status": "FAILED", "error_code": "INTERRUPTED"}))
    assert store.read_run("test_buyer1", "run1").error_code == "INTERRUPTED"
    assert len(store.list_runs("test_buyer1")) == 1
    rows = store._query("test_buyer1", '''
        SELECT (COUNT(?event) AS ?n) WHERE { GRAPH <urn:procurement:test_buyer1:run:run1> {
          ?event a <urn:procurement:vocab:RunEvent>.
        } }
    ''')["results"]["bindings"]
    assert rows[0]["n"]["value"] == "2"


def test_publish_conflict_and_rollback(store, monkeypatch):
    from procurement_ontology.store import VersionConflict

    store.provision_company("test_buyer1", current_platform_versions(store))
    old = store.read_current("test_buyer1", "ontology")
    snapshot = PublishedSnapshot(id="new-version", kind="ontology", payload={"items": [], "relations": []},
                                 previous_id=old.id, created_by="buyer-reviewer")
    actual_update = store._update

    def fail_after_write(scope_id, update):
        return actual_update(scope_id, update + "; LOAD <file:///procurement-store-fault.ttl> INTO GRAPH <urn:fault>")

    with monkeypatch.context() as patch:
        patch.setattr(store, "_update", fail_after_write)
        with pytest.raises(requests.HTTPError):
            store.publish("test_buyer1", "ontology", snapshot, old.id)
    assert store.read_current("test_buyer1", "ontology") == old
    assert store.read_version("test_buyer1", "ontology", "new-version") is None
    store.publish("test_buyer1", "ontology", snapshot, old.id)
    assert store.read_current("test_buyer1", "ontology") == snapshot
    with pytest.raises(VersionConflict):
        store.publish("test_buyer1", "ontology", snapshot.model_copy(update={"id": "stale"}), old.id)


def test_two_publishers_cannot_overwrite_each_other(store):
    from procurement_ontology.store import VersionConflict

    store.provision_company("test_buyer1", current_platform_versions(store))
    old = store.read_current("test_buyer1", "ontology")

    def publish(name):
        snapshot = PublishedSnapshot(id=name, kind="ontology", payload={"items": [], "relations": []},
                                     previous_id=old.id, created_by="buyer-reviewer")
        try:
            store.publish("test_buyer1", "ontology", snapshot, old.id)
            return True
        except VersionConflict:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(publish, ["v2a", "v2b"]))
    assert outcomes.count(True) == 1
    assert store.read_version("test_buyer1", "ontology", old.id) == old
