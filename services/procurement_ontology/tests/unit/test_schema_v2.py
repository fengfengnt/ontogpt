"""Combined enterprise v2 templates preserve v1 and all archived additions."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
import yaml
from linkml.generators.pydanticgen import PydanticGenerator
from pydantic import ValidationError

from ontogpt.io.utils import ensure_utf8_coding_cookie
from procurement_ontology.extraction import normalize_candidates
from procurement_ontology.models import ExtractionRun, SourceRevision
from procurement_ontology.schema_loader import load_registered_template

ROOT = Path(__file__).resolve().parents[4]
ARCHIVE = ROOT / "docs/procurement-ontology/schema-drafts"


@pytest.mark.parametrize("company,count", [("test_buyer1", 7), ("test_supplier1", 3)])
def test_v2_preserves_v1_and_combines_archived_additions(company, count, tmp_path, monkeypatch):
    v1 = load_registered_template(company, "computer", "v1")
    v2 = load_registered_template(company, "computer", "v2")
    base = yaml.safe_load(v1.yaml_path.read_text(encoding="utf-8"))
    combined = yaml.safe_load(v2.yaml_path.read_text(encoding="utf-8"))
    remaining = copy.deepcopy(combined)
    drafts = [draft for draft in json.loads((ARCHIVE / "manifest.json").read_text(encoding="utf-8"))["drafts"]
              if draft["company_id"] == company]
    assert len(drafts) == count
    for draft in drafts:
        assert v1.yaml_sha256 == draft["base_artifacts"]["yaml_sha256"]
        assert v1.python_sha256 == draft["base_artifacts"]["python_sha256"]
        proposal = draft["proposal"]
        original = yaml.safe_load((ARCHIVE / draft["artifacts"]["yaml"]["path"]).read_text(encoding="utf-8"))
        if proposal["operation"] == "add_field":
            attrs = remaining["classes"][proposal["target_class"]]["attributes"]
            assert attrs.pop(proposal["name"]) == original["classes"][proposal["target_class"]]["attributes"][proposal["name"]]
        else:
            enum = "BuyerRelationType"
            assert remaining["enums"][enum]["permissible_values"].pop(proposal["name"]) == original["enums"][enum]["permissible_values"][proposal["name"]]
    assert remaining.pop("version") == "v2"
    assert remaining == base
    assert v2.root_class == v1.root_class
    assert v2.python_class.model_validate({}).model_dump() == v1.python_class.model_validate({}).model_dump()
    group = "collection_fields" if company == "test_buyer1" else "project_evidence"
    legacy = {group: [{"label": "v1 已有条目", "statement": "保留原文陈述", "evidence_quote": "保留原文"}]}
    assert v2.python_class.model_validate(legacy).model_dump(exclude_none=True) == v1.python_class.model_validate(legacy).model_dump(exclude_none=True)
    relative_yaml = v2.yaml_path.relative_to(ROOT)
    copied_yaml = tmp_path / relative_yaml
    copied_yaml.parent.mkdir(parents=True)
    copied_yaml.write_bytes(v2.yaml_path.read_bytes())
    monkeypatch.chdir(tmp_path)
    generated = ensure_utf8_coding_cookie(PydanticGenerator(relative_yaml.as_posix()).serialize())
    assert generated.encode("utf-8") == v2.python_path.read_bytes()


@pytest.mark.parametrize("company,payload", [
    ("test_buyer1", {
        "collection_fields": [{"procurement_unit_price": 4999.5}],
        "condition_templates": [{"local_ref": "a", "quotation_inclusions": "运费", "volume_discount_tier": "50台专项折扣",
                                 "acceptance_inspection_ratio": "20%"}, {"local_ref": "b", "condition_text": "仅送修"}],
        "term_definitions": [{"brand_pool_membership": "联想属于本项目品牌池"}],
        "process_notes": [{"evaluation_committee_size": 5}],
        "relations": [{"subject_ref": "a", "predicate": "conflicts_with", "object_ref": "b"}],
    }),
    ("test_supplier1", {
        "project_evidence": [{"invited_supplier_names": "戴尔、惠普"}],
        "pricing_strategies": [{"payment_terms_text": "验收后支付90%", "late_payment_penalty_text": "每日万分之五，上限5%"}],
    }),
])
def test_v2_values_survive_validation_and_candidate_normalization(company, payload):
    binding = load_registered_template(company, "computer", "v2")
    quote = "仅用于离线结构验证的模拟材料"
    payload = copy.deepcopy(payload)
    for rows in payload.values():
        for row in rows:
            row["evidence_quote"] = quote
    extracted = binding.python_class.model_validate(payload)
    source = SourceRevision(id="v2-test-source", scope_id=company, text=quote, simulated=True,
                            sha256=hashlib.sha256(quote.encode()).hexdigest(), submitted_by="test-reviewer")
    run = ExtractionRun(id="v2-test-run", scope_id=company, revision_id=source.id, category_key="computer",
                        schema_version="v2", yaml_sha256=binding.yaml_sha256, python_sha256=binding.python_sha256,
                        requested_by="test-reviewer", batch_id="v2-test-batch")
    candidates, suggestions = normalize_candidates(binding, source, run, extracted, "computer-category")
    assert suggestions == []
    assert len(candidates) == sum(len(rows) for rows in payload.values())
    for group, rows in payload.items():
        for row in rows:
            if group == "relations":
                relation = next(candidate for candidate in candidates if hasattr(candidate.item, "predicate")
                                and candidate.item.predicate == "conflicts_with")
                assert relation.status == "PENDING_REVIEW"
                ids = {candidate.item.id for candidate in candidates if hasattr(candidate.item, "properties")}
                assert relation.item.subject_id in ids and relation.item.object_id in ids
            else:
                properties = {key: value for key, value in row.items() if key not in {"local_ref", "evidence_quote"}}
                assert any(all(candidate.item.properties.get(key) == value for key, value in properties.items())
                           for candidate in candidates if hasattr(candidate.item, "properties"))
    for candidate in candidates:
        assert candidate.item.source_spans[0].quote == quote
        if hasattr(candidate.item, "schema_version"):
            assert candidate.item.schema_version == "v2"


@pytest.mark.parametrize("company,payload", [
    ("test_buyer1", {"collection_fields": [{"procurement_unit_price": "invalid-price"}]}),
    ("test_buyer1", {"process_notes": [{"evaluation_committee_size": "invalid-count"}]}),
    ("test_buyer1", {"pricing_strategies": [{"payment_terms_text": "跨企业字段"}]}),
    ("test_supplier1", {"relations": [{"predicate": "conflicts_with"}]}),
])
def test_v2_rejects_invalid_types_and_other_enterprise_fields(company, payload):
    binding = load_registered_template(company, "computer", "v2")
    with pytest.raises(ValidationError):
        binding.python_class.model_validate(payload)


@pytest.mark.parametrize("field", [
    "quotation_inclusions", "brand_pool_membership", "volume_discount_tier", "late_payment_penalty_text",
])
def test_supplemental_simulated_samples_keep_values_evidence_and_scope(field):
    fixture = ROOT / "services/procurement_ontology/tests/fixtures/schema-v2-synthetic.yaml"
    samples = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    assert samples["simulated"] is True
    case = next(case for case in samples["positive_cases"] if case["field"] == field)
    binding = load_registered_template(case["company_id"], "computer", "v2")
    text, quote = case["text"], case["value"]
    start = text.index(quote)
    row = {field: quote, "evidence_quote": quote, "evidence_start": start, "evidence_end": start + len(quote),
           "project_ref": case["project_ref"], "stage": case["stage"]}
    extracted = binding.python_class.model_validate({case["group"]: [row]})
    source = SourceRevision(id=field, scope_id=case["company_id"], text=text, simulated=True,
                            sha256=hashlib.sha256(text.encode()).hexdigest(), submitted_by="synthetic-test")
    run = ExtractionRun(id=field, scope_id=source.scope_id, revision_id=source.id, category_key="computer",
                        schema_version="v2", yaml_sha256=binding.yaml_sha256, python_sha256=binding.python_sha256,
                        requested_by="synthetic-test", batch_id=field)
    candidates, suggestions = normalize_candidates(binding, source, run, extracted, "simulated-computer")
    assert not suggestions and len(candidates) == 1
    candidate = candidates[0]
    assert candidate.status == "PENDING_REVIEW"
    assert candidate.item.properties[field] == quote
    assert candidate.item.simulated is True
    assert candidate.item.schema_version == "v2"
    assert candidate.item.scope.project_ref == case["project_ref"]
    assert candidate.item.scope.stage == case["stage"]
    assert len(candidate.item.source_spans) == 1
    candidate.item.source_spans[0].validate_against(source)
