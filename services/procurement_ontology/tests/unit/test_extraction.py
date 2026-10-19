"""Run real prompt/schema/normalization code; replace only external model/storage IO."""

import copy
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from procurement_ontology.identity import Identity
from procurement_ontology.schema_loader import load_registered_template

BUYER = Identity("buyer-admin", "test_buyer1", "company_admin")
SUPPLIER = Identity("supplier-admin", "test_supplier1", "company_admin")


class MemoryStore:
    def __init__(self):
        self.sources, self.runs, self.batches = {}, {}, {}

    def append_source(self, scope, source):
        self.sources[scope, source.id] = copy.deepcopy(source)

    def read_source(self, scope, source_id):
        return copy.deepcopy(self.sources.get((scope, source_id)))

    def save_run(self, scope, run):
        self.runs[scope, run.id] = copy.deepcopy(run)

    def read_run(self, scope, run_id):
        return copy.deepcopy(self.runs.get((scope, run_id)))

    def list_runs(self, scope):
        return [copy.deepcopy(run) for (company, _), run in self.runs.items() if company == scope]

    def append_candidates(self, scope, batch_id, candidates):
        self.batches[scope, batch_id] = copy.deepcopy(candidates)

    def read_current(self, scope, kind):
        from procurement_ontology.models import PublishedSnapshot
        return PublishedSnapshot(id="tree-v1", kind="tree", created_by="system",
                                 payload={"category_keys": {"computer": scope + ":computer"}, "nodes": []})


class Catalog:
    def __init__(self):
        self.bindings = {company: load_registered_template(company, "computer", "v1")
                         for company in ("test_buyer1", "test_supplier1")}

    def active(self, company, category):
        return self.bindings[company]


class Client:
    def __init__(self, *responses, during_call=None):
        self.responses = list(responses)
        self.during_call = during_call

    def complete(self, prompt, show_prompt=False):
        if self.during_call:
            self.during_call()
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return json.dumps(response, ensure_ascii=False)


def buyer_payload(quote="原厂上门"):
    return {"collection_fields": [{"local_ref": "warranty", "label": "保修方式",
                                    "statement": "采集服务方式", "question": "上门还是送修？",
                                    "evidence_quote": quote, "device_type": "办公笔记本",
                                    "project_ref": "PRO-IT-2026-014"}]}


def services(client, store=None, catalog=None):
    from procurement_ontology.intake import IntakeService
    from procurement_ontology.extraction import ExtractionService

    store, catalog = store or MemoryStore(), catalog or Catalog()
    return IntakeService(store), ExtractionService(store, catalog, client_factory=lambda binding: client), store, catalog


def test_buyer_and_supplier_use_own_schema():
    intake, extractor, store, _ = services(Client(buyer_payload()))
    revision = intake.submit(BUYER, "原厂上门", simulated=True)
    run = extractor.extract(BUYER, revision.id, "computer")
    candidate = store.batches[BUYER.scope_id, run.batch_id][0]
    assert run.status == "SUCCEEDED"
    assert candidate.item.kind == "CollectionField"
    assert candidate.item.category_id == "test_buyer1:computer"
    assert candidate.item.scope.project_ref == "PRO-IT-2026-014"
    assert candidate.item.simulated is True
    intake, extractor, store, _ = services(Client({"cost_items": [{
        "local_ref": "cost", "label": "迁移人工成本", "statement": "本项目迁移成本为 1200 元",
        "evidence_quote": "迁移成本 1200 元", "amount_text": "1200 元", "project_ref": "BID-IT-2026-014",
    }]}))
    revision = intake.submit(SUPPLIER, "迁移成本 1200 元", simulated=True)
    run = extractor.extract(SUPPLIER, revision.id, "computer")
    candidate = store.batches[SUPPLIER.scope_id, run.batch_id][0]
    assert candidate.item.kind == "InternalCost"
    assert candidate.item.properties["amount_text"] == "1200 元"
    assert candidate.item.category_id == "test_supplier1:computer"


@pytest.mark.parametrize("text,quote", [("上门。上门", "上门"), ("aaaa", "aaa")])
def test_ambiguous_quote_stays_unverified(text, quote):
    intake, extractor, store, _ = services(Client(buyer_payload(quote)))
    revision = intake.submit(BUYER, text, simulated=True)
    run = extractor.extract(BUYER, revision.id, "computer")
    candidate = store.batches[BUYER.scope_id, run.batch_id][0]
    assert candidate.status == "MODEL_SUGGESTION"
    assert candidate.item.source_spans == []


def test_original_unicode_offsets():
    intake, extractor, store, _ = services(Client(buyer_payload()))
    revision = intake.submit(BUYER, "原厂😀\r\n原厂上门", simulated=True)
    run = extractor.extract(BUYER, revision.id, "computer")
    span = store.batches[BUYER.scope_id, run.batch_id][0].item.source_spans[0]
    assert (span.start, span.end, span.quote) == (5, 9, "原厂上门")
    assert store.read_source(BUYER.scope_id, revision.id).text == "原厂😀\r\n原厂上门"


def test_retry_keeps_one_run():
    intake, extractor, store, _ = services(Client(buyer_payload()))
    revision = intake.submit(BUYER, "原厂上门", simulated=True)
    first = extractor.extract(BUYER, revision.id, "computer")
    second = extractor.extract(BUYER, revision.id, "computer")
    assert first.id == second.id
    assert second.status == "SUCCEEDED"
    assert len(store.runs) == 1
    assert len(store.batches[BUYER.scope_id, second.batch_id]) == 1


def test_failure_keeps_source_and_can_be_retried():
    intake, extractor, store, _ = services(Client(RuntimeError("provider failure"), buyer_payload()))
    revision = intake.submit(BUYER, "原厂上门", simulated=True)
    failed = extractor.extract(BUYER, revision.id, "computer")
    assert failed.status == "FAILED"
    assert store.read_source(BUYER.scope_id, revision.id) == revision
    assert store.batches == {}
    retried = extractor.extract(BUYER, revision.id, "computer")
    assert retried.id == failed.id
    assert retried.status == "SUCCEEDED"


def test_binding_does_not_change_during_model_call():
    catalog = Catalog()
    initial = catalog.bindings[BUYER.scope_id]
    client = Client(buyer_payload(), during_call=lambda: catalog.bindings.update({BUYER.scope_id: replace(initial, version="v2")}))
    intake, extractor, store, _ = services(client, catalog=catalog)
    revision = intake.submit(BUYER, "原厂上门", simulated=True)
    run = extractor.extract(BUYER, revision.id, "computer")
    assert run.schema_version == "v1"
    assert store.batches[BUYER.scope_id, run.batch_id][0].item.schema_version == "v1"
    assert catalog.active(BUYER.scope_id, "computer").version == "v2"


def test_source_id_cannot_cross_company():
    intake, extractor, _, _ = services(Client(buyer_payload()))
    revision = intake.submit(BUYER, "原厂上门", simulated=True)
    with pytest.raises(ValueError):
        extractor.extract(SUPPLIER, revision.id, "computer")


def test_service_model_client_disables_cache_and_material_logging(tmp_path, monkeypatch, caplog):
    import procurement_ontology.model_client as module

    monkeypatch.chdir(tmp_path)
    transmitted = {}

    def provider(**kwargs):
        transmitted.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))])

    monkeypatch.setattr(module, "completion", provider)
    client = module.ServiceLLMClient(model="openai/test-model", api_key="synthetic-key")
    assert client.complete("仅测试：内部成本和报价材料", show_prompt=True) == '{"ok":true}'
    assert transmitted["caching"] is False
    assert "仅测试：内部成本和报价材料" not in caplog.text
    assert not (tmp_path / ".litellm_cache").exists()


def test_interrupted_run_is_recoverable_without_publishing():
    intake, extractor, store, _ = services(Client(buyer_payload()))
    revision = intake.submit(BUYER, "原厂上门", simulated=True)
    run = extractor.extract(BUYER, revision.id, "computer")
    run.status = "RUNNING"
    store.save_run(BUYER.scope_id, run)
    assert extractor.recover_interrupted(BUYER.scope_id) == 1
    recovered = store.read_run(BUYER.scope_id, run.id)
    assert (recovered.status, recovered.error_code) == ("FAILED", "INTERRUPTED")
    assert extractor.recover_interrupted(SUPPLIER.scope_id) == 0


def test_relation_endpoints_resolve_only_within_the_run():
    payload = buyer_payload()
    payload["collection_fields"].append({"local_ref": "service", "label": "服务地点", "evidence_quote": "原厂上门"})
    payload["relations"] = [
        {"subject_ref": "warranty", "predicate": "requires_information", "object_ref": "service", "evidence_quote": "原厂上门"},
        {"subject_ref": "warranty", "predicate": "requires_information", "object_ref": "other-company:item", "evidence_quote": "原厂上门"},
    ]
    intake, extractor, store, _ = services(Client(payload))
    revision = intake.submit(BUYER, "原厂上门", simulated=True)
    run = extractor.extract(BUYER, revision.id, "computer")
    relations = [candidate for candidate in store.batches[BUYER.scope_id, run.batch_id] if hasattr(candidate.item, "predicate")]
    assert len(relations) == 2
    assert relations[0].status == "PENDING_REVIEW"
    assert relations[1].status == "MODEL_SUGGESTION"
    assert relations[1].item.object_id.startswith("unresolved:")
