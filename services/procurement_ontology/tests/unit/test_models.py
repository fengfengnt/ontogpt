"""Tests for evidence and category validation at the service boundary."""

import hashlib
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError


def test_span_matches_source():
    from procurement_ontology.models import SourceRevision, SourceSpan

    text = "甲方😀\r\n原厂上门"
    source = SourceRevision(
        id="src1", scope_id="test_buyer1", text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        simulated=True, submitted_by="reviewer1", created_at=datetime.now(timezone.utc),
    )
    span = SourceSpan(revision_id="src1", start=5, end=9, quote="原厂上门")
    span.validate_against(source)
    assert source.text[span.start:span.end] == "原厂上门"
    with pytest.raises(ValueError):
        SourceSpan(revision_id="src1", start=4, end=8, quote="原厂上门").validate_against(source)
    with pytest.raises(ValueError):
        SourceSpan(revision_id="other", start=5, end=9, quote="原厂上门").validate_against(source)


@pytest.mark.parametrize("level,parent", [(0, None), (4, "p"), (1, "p"), (2, None)])
def test_category_level_is_one_to_three(level, parent):
    from procurement_ontology.models import CategoryNode

    with pytest.raises(ValidationError):
        CategoryNode(id="cat", label="电脑", level=level, parent_id=parent)


def test_valid_category_path_preserves_stable_ids():
    from procurement_ontology.models import CategoryNode

    nodes = [
        CategoryNode(id="root", label="IT与通讯", level=1),
        CategoryNode(id="office", label="办公设备", level=2, parent_id="root"),
        CategoryNode(id="computer", label="电脑(台式机/笔记本)", level=3, parent_id="office"),
    ]
    assert [(node.id, node.parent_id) for node in nodes] == [
        ("root", None), ("office", "root"), ("computer", "office"),
    ]


def test_source_hash_must_describe_saved_text():
    from procurement_ontology.models import SourceRevision

    with pytest.raises(ValidationError):
        SourceRevision(
            id="src1", scope_id="test_supplier1", text="模拟报价",
            sha256="0" * 64, simulated=True, submitted_by="supplier_admin",
            created_at=datetime.now(timezone.utc),
        )


def test_candidate_without_evidence_cannot_be_accepted():
    from procurement_ontology.models import Candidate, KnowledgeItem

    item = KnowledgeItem(
        id="item1", kind="InternalCost", label="项目成本", description="模拟成本陈述",
        category_id="computer", scope={"project_ref": "BID-IT-2026-014"},
    )
    candidate = Candidate(id="candidate1", item=item)
    assert candidate.status == "MODEL_SUGGESTION"
    assert item.access_policy_ref is None
    assert item.scope.project_ref == "BID-IT-2026-014"
    with pytest.raises(ValidationError):
        Candidate(id="candidate1", item=item, status="ACCEPTED")


def test_accepted_relation_requires_its_own_evidence():
    from procurement_ontology.models import Candidate, KnowledgeRelation, SourceSpan

    relation = KnowledgeRelation(
        id="rel1", subject_id="offer1", predicate="provides_service", object_id="service1",
        source_spans=[SourceSpan(revision_id="src1", start=0, end=4, quote="原厂上门")],
    )
    candidate = Candidate(id="candidate1", item=relation, status="ACCEPTED")
    assert candidate.item.predicate == "provides_service"
