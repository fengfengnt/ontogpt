import json
from types import SimpleNamespace

from test_store import current_platform_versions, store
from procurement_ontology.extraction import ExtractionService
from procurement_ontology.identity import Identity
from procurement_ontology.intake import IntakeService
from procurement_ontology.schema_loader import load_registered_template


def test_partial_candidate_write_retry_has_one_current_batch(store, monkeypatch):
    actor = Identity("buyer", "test_buyer1", "company_admin")
    store.provision_company(actor.scope_id, current_platform_versions(store))
    original_append = store.append_candidates
    intercepted = False

    def partial(scope, batch_id, candidates):
        nonlocal intercepted
        if not intercepted:
            intercepted = True
            original_append(scope, batch_id, candidates[:1])
            raise ConnectionError("interrupted after first immutable candidate")
        original_append(scope, batch_id, candidates)

    monkeypatch.setattr(store, "append_candidates", partial)
    completions = iter(["保修方式", "保修方式修订"])

    class Client:
        model = "synthetic/retry"

        def complete(self, prompt, show_prompt=False):
            return json.dumps({"collection_fields": [
                {"label": next(completions), "evidence_quote": "原厂上门"},
                {"label": "服务地点", "evidence_quote": "原厂上门"},
            ]})

    catalog = SimpleNamespace(active=lambda company, category: load_registered_template(company, category, "v1"))
    extractor = ExtractionService(store, catalog, client_factory=lambda binding: Client())
    source = IntakeService(store).submit(actor, "原厂上门", True)
    first = extractor.extract(actor, source.id, "computer")
    assert first.status == "FAILED" and len(store.read_batch(actor.scope_id, first.batch_id)) == 1
    retried = extractor.extract(actor, source.id, "computer")
    assert retried.id == first.id and retried.status == "SUCCEEDED"
    assert retried.batch_id != first.batch_id
    assert len(store.read_batch(actor.scope_id, retried.batch_id)) == 2
    assert len(store.read_batch(actor.scope_id, first.batch_id)) == 1
