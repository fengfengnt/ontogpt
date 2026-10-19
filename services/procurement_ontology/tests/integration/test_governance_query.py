"""Governance boundaries exercised against real, isolated TDB2 datasets."""

import copy
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from test_store import current_platform_versions, source, store
from procurement_ontology.identity import Identity
from procurement_ontology.models import Applicability, Candidate, ExtractionRun, KnowledgeItem, PublishedSnapshot, SourceSpan
from procurement_ontology.schema_loader import load_registered_template

BUYER = Identity("buyer", "test_buyer1", "company_admin")
SUPPLIER = Identity("supplier", "test_supplier1", "company_admin")
PLATFORM = Identity("platform", "platform", "platform_admin")


class Catalog:
    def active(self, company, category):
        return load_registered_template(company, category, "v1")


@pytest.fixture
def services(store):
    from procurement_ontology.governance import GovernanceService
    from procurement_ontology.query import KnowledgeQuery
    for company in (BUYER.scope_id, SUPPLIER.scope_id):
        store.provision_company(company, current_platform_versions(store))
    return GovernanceService(store, Catalog()), KnowledgeQuery(store), store


def propose(services, actor=BUYER, label="保修方式", amount=None, identifier="item1", revision="src1", text="原厂上门"):
    governance, query, store = services
    original = source(actor.scope_id, text).model_copy(update={"id": revision})
    store.append_source(actor.scope_id, original)
    item = KnowledgeItem(id=identifier, kind="InternalCost" if amount else "CollectionField", label=label,
                         category_id=actor.scope_id + ":computer", simulated=True, schema_version="v1",
                         scope=Applicability(project_ref="BID-IT-2026-014") if amount else Applicability(),
                         properties={"amount_text": amount, "cost_type": "迁移人工"} if amount else {},
                         source_spans=[SourceSpan(revision_id=revision, start=0, end=len(text), quote=text)])
    run = ExtractionRun(id="run-" + identifier, scope_id=actor.scope_id, revision_id=revision, category_key="computer",
                        schema_version="v1", yaml_sha256="a" * 64, python_sha256="b" * 64,
                        batch_id="batch-" + identifier, requested_by=actor.account_id, status="SUCCEEDED",
                        candidate_ids=["candidate-" + identifier])
    store.save_run(actor.scope_id, run)
    store.append_candidates(actor.scope_id, run.batch_id, [Candidate(id="candidate-" + identifier, item=item, extraction_run_id=run.id)])
    return run, item


def test_unpublished_is_invisible(services):
    governance, query, store = services
    run, item = propose(services)
    assert query.search(BUYER, "保修", "computer")["items"] == []
    batch = governance.review(BUYER, "candidate-item1", "ACCEPTED")
    assert query.search(BUYER, "保修", "computer")["items"] == []
    snapshot = governance.publish(BUYER, "ontology", batch.id)
    result = query.search(BUYER, "保修", "computer")
    assert result["items"][0]["id"] == item.id
    assert result["versions"]["ontology"] == snapshot.id
    detail = query.get(BUYER, item.id, result["versions"])
    assert detail["item"]["simulated"] is True
    assert detail["sources"][0]["quote"] == "原厂上门"
    assert [node["level"] for node in detail["category_path"]] == [1, 2, 3]
    assert query.search(SUPPLIER, "保修", "computer")["items"] == []
    with pytest.raises(KeyError):
        query.get(SUPPLIER, item.id)


def test_referenced_category_cannot_be_deleted(services):
    governance, query, _ = services
    propose(services)
    batch = governance.review(BUYER, "candidate-item1", "ACCEPTED")
    governance.publish(BUYER, "ontology", batch.id)
    with pytest.raises(ValueError, match="引用"):
        batch = governance.edit_tree(BUYER, {"op": "remove_node", "id": "test_buyer1:computer"}, query.versions(BUYER))
        governance.publish(BUYER, "tree", batch.id)


def test_platform_and_company_write_scopes(services):
    governance, query, _ = services
    with pytest.raises(PermissionError):
        governance.edit_tree(PLATFORM, {"op": "update_node", "scope_id": "test_buyer1", "node": {}}, query.versions(PLATFORM))
    with pytest.raises(PermissionError):
        governance.edit_tree(BUYER, {"op": "update_node", "scope_id": "test_supplier1", "node": {}}, query.versions(BUYER))
    batch = governance.edit_tree(PLATFORM, {"op": "update_node", "node": {"id": "computer", "level": 3, "parent_id": "office", "label": "通用电脑"}}, query.versions(PLATFORM))
    governance.publish(PLATFORM, "tree", batch.id)
    assert query.tree(PLATFORM)["nodes"][-1]["label"] == "通用电脑"
    assert query.tree(BUYER)["nodes"][-1]["label"] != "通用电脑"


def test_observed_version_conflict(services):
    from procurement_ontology.store import VersionConflict
    governance, query, _ = services
    observed = query.versions(BUYER)
    first = governance.edit_tree(BUYER, {"op": "update_node", "node": {"id": "test_buyer1:computer", "level": 3, "parent_id": "test_buyer1:office", "label": "电脑"}}, observed)
    stale = governance.edit_tree(BUYER, {"op": "update_node", "node": {"id": "test_buyer1:computer", "level": 3, "parent_id": "test_buyer1:office", "label": "旧提交"}}, observed)
    governance.publish(BUYER, "tree", first.id)
    with pytest.raises(VersionConflict):
        governance.publish(BUYER, "tree", stale.id)
    with pytest.raises(VersionConflict):
        query.get(BUYER, "missing", observed)
    with pytest.raises(VersionConflict):
        governance.edit_item(BUYER, {"op": "remove_item", "id": "missing"}, observed)


def test_cost_conflict_is_not_silently_overwritten(services):
    governance, query, _ = services
    propose(services, SUPPLIER, "迁移人工成本", "600 元", text="迁移人工成本600元")
    first = governance.review(SUPPLIER, "candidate-item1", "ACCEPTED")
    governance.publish(SUPPLIER, "ontology", first.id)
    propose(services, SUPPLIER, "迁移人工成本", "1200 元", identifier="item2", revision="src2", text="迁移人工成本1200元")
    second = governance.review(SUPPLIER, "candidate-item2", "ACCEPTED")
    with pytest.raises(ValueError, match="冲突"):
        governance.publish(SUPPLIER, "ontology", second.id)
    assert query.search(SUPPLIER, "迁移", "computer")["items"][0]["properties"]["amount_text"] == "600 元"


def test_forged_evidence_and_unresolved_relation_are_rejected(services):
    governance, query, _ = services
    _, item = propose(services)
    item.source_spans[0].quote = "伪造"
    with pytest.raises(ValueError, match="原文|span"):
        governance.edit_item(BUYER, {"op": "add_item", "item": item.model_dump(mode="json")}, query.versions(BUYER))
    with pytest.raises(ValueError):
        governance.edit_item(BUYER, {"op": "add_relation", "relation": {"id": "bad", "subject_id": "other:item", "predicate": "new_unactivated_relation", "object_id": "item1", "source_spans": []}}, query.versions(BUYER))


def test_category_parent_and_operation_boundaries(services):
    governance, query, _ = services
    observed = query.versions(BUYER)
    with pytest.raises(ValueError):
        governance.edit_tree(BUYER, {"op": "add_node", "node": {"id": "invalid", "level": 3, "parent_id": "test_buyer1:it", "label": "跳层"}}, observed)
    with pytest.raises(ValueError):
        governance.edit_item(BUYER, {"op": "remove_node", "id": "test_buyer1:computer"}, observed)


def test_reader_cannot_review_or_edit(services):
    governance, query, _ = services
    reader = Identity("reader", BUYER.scope_id, "reader")
    with pytest.raises(PermissionError):
        governance.review(reader, "guessed", "ACCEPTED")
    with pytest.raises(PermissionError):
        governance.edit_tree(reader, {"op": "remove_node", "id": "guessed"}, query.versions(reader))


def test_failed_run_candidates_cannot_enter_review(services):
    governance, _, store = services
    run, _ = propose(services)
    run.status = "FAILED"
    store.save_run(BUYER.scope_id, run)
    with pytest.raises(ValueError):
        governance.review(BUYER, "candidate-item1", "ACCEPTED")


def test_manual_edits_must_match_active_schema_and_keep_cost_project(services):
    governance, query, _ = services
    _, item = propose(services)
    item.kind = "UnregisteredClass"
    with pytest.raises(ValueError, match="schema"):
        governance.edit_item(BUYER, {"op": "add_item", "item": item.model_dump(mode="json")}, query.versions(BUYER))
    _, cost = propose(services, SUPPLIER, "迁移成本", "600 元")
    cost.scope.project_ref = None
    with pytest.raises(ValueError, match="项目"):
        governance.edit_item(SUPPLIER, {"op": "add_item", "item": cost.model_dump(mode="json")}, query.versions(SUPPLIER))


def test_publication_retry_repairs_missing_audit_event(services, monkeypatch):
    governance, query, store = services
    propose(services)
    batch = governance.review(BUYER, "candidate-item1", "ACCEPTED")
    original = store.save_change_batch

    def fail_once(scope, value):
        if value.status == "PUBLISHED":
            monkeypatch.setattr(store, "save_change_batch", original)
            raise ConnectionError("response interrupted after publication")
        return original(scope, value)

    monkeypatch.setattr(store, "save_change_batch", fail_once)
    with pytest.raises(ConnectionError):
        governance.publish(BUYER, "ontology", batch.id)
    published = governance.publish(BUYER, "ontology", batch.id)
    recovered = store.read_change_batch(BUYER.scope_id, batch.id)
    assert recovered.status == "PUBLISHED"
    assert recovered.audit[-1]["action"] == "publish"
    assert query.versions(BUYER)["ontology"] == published.id


def test_tree_and_ontology_publish_compare_both_pointers_atomically(services):
    from procurement_ontology.store import VersionConflict
    _, query, store = services
    pair = store.read_pair(BUYER.scope_id)
    observed = query.versions(BUYER)
    barrier = threading.Barrier(2)

    def publish(kind):
        snapshot = PublishedSnapshot(id="concurrent-" + kind, kind=kind, payload=copy.deepcopy(pair[kind].payload),
                                     previous_id=pair[kind].id, created_by=BUYER.account_id)
        barrier.wait(timeout=10)
        try:
            store.publish(BUYER.scope_id, kind, snapshot, pair[kind].id, expected_versions=observed)
            return "published"
        except VersionConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(publish, ("tree", "ontology"))) == ["conflict", "published"]


def test_case_threshold_requires_project_scope(services):
    governance, query, _ = services
    _, item = propose(services)
    item.kind = "ConditionTemplate"
    item.properties = {"case_threshold": "本项目要求三年保修", "condition_category": "technical"}
    with pytest.raises(ValueError, match="项目"):
        governance.edit_item(BUYER, {"op": "add_item", "item": item.model_dump(mode="json")}, query.versions(BUYER))
