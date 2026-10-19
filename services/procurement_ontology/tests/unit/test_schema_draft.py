"""Schema suggestions can only create additive artifacts in a separate Git worktree."""

import hashlib
import importlib.util
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from procurement_ontology.models import SourceRevision, SourceSpan
from procurement_ontology.schema_loader import load_registered_template


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def workspace(tmp_path):
    repo, draft = tmp_path / "running", tmp_path / "draft"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    (repo / ".gitattributes").write_text("*.yaml text eol=lf\n*.py text eol=lf\n", encoding="utf-8")
    original = load_registered_template("test_buyer1", "computer", "v1")
    relative = Path("src/ontogpt/templates/company/test_buyer1/computer/v1")
    shutil.copytree(original.yaml_path.parent, repo / relative)
    git(repo, "add", ".")
    git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "test schema")
    git(repo, "worktree", "add", "-b", "codex/schema-draft/test-gap", str(draft))
    binding = replace(original, yaml_path=repo / relative / original.yaml_path.name,
                      python_path=repo / relative / original.python_path.name)
    source = SourceRevision(id="s1", scope_id="test_buyer1", text="新增远程部署支持信息", simulated=True,
                            sha256=hashlib.sha256("新增远程部署支持信息".encode()).hexdigest(), submitted_by="reviewer")
    span = SourceSpan(revision_id=source.id, start=0, end=len(source.text), quote=source.text)
    return repo, draft, binding, source, span


def test_new_relation_generates_draft(workspace):
    from procurement_ontology.schema_draft import detect_gap, draft_additive_schema
    repo, draft, binding, source, span = workspace
    gap = detect_gap(binding, span, {"operation": "add_relation", "name": "supports_remote_deployment", "description": "支持远程部署"}, source=source)
    artifacts = draft_additive_schema(gap, draft, binding=binding)
    result = yaml.safe_load(artifacts.yaml_path.read_text(encoding="utf-8"))
    assert artifacts.version == "v2"
    assert "supports_remote_deployment" in result["enums"]["BuyerRelationType"]["permissible_values"]
    assert hashlib.sha256(binding.yaml_path.read_bytes()).hexdigest() == binding.yaml_sha256
    assert hashlib.sha256(binding.python_path.read_bytes()).hexdigest() == binding.python_sha256
    assert artifacts.python_path.is_file()
    # Only generated code, never model-provided Python, is imported in this test process.
    spec = importlib.util.spec_from_file_location("generated_draft", artifacts.python_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.BuyerComputerExtraction.model_rebuild(_types_namespace=vars(module))
    assert module.BuyerComputerExtraction.model_validate({})
    assert "schema_registry.yaml" not in git(draft, "status", "--porcelain")
    assert git(repo, "status", "--porcelain") == ""


@pytest.mark.parametrize("proposal", [
    {"operation": "rename", "name": "new_name", "description": "改名"},
    {"operation": "delete", "name": "question", "description": "删除"},
    {"operation": "add_field", "name": "question", "target_class": "CollectionField", "range": "integer", "description": "改变类型"},
    {"operation": "add_field", "name": "new_value", "target_class": "OtherCompanyClass", "description": "跨企业"},
    {"operation": "add_relation", "name": "../../escape", "description": "越界"},
    {"operation": "add_relation", "name": "safe", "description": "隐藏源码", "python": "print('bad')"},
])
def test_rename_or_type_change_is_rejected(workspace, proposal):
    from procurement_ontology.schema_draft import detect_gap
    _, _, binding, source, span = workspace
    with pytest.raises(ValueError):
        detect_gap(binding, span, proposal, source=source)


def test_wrong_git_branch_is_rejected(workspace):
    from procurement_ontology.schema_draft import detect_gap, draft_additive_schema
    repo, draft, binding, source, span = workspace
    gap = detect_gap(binding, span, {"operation": "add_field", "name": "remote_service", "target_class": "CollectionField", "range": "string", "description": "部署方式"}, source=source)
    git(draft, "switch", "-c", "unreviewed")
    with pytest.raises(ValueError, match="分支"):
        draft_additive_schema(gap, draft, binding=binding)
    with pytest.raises(ValueError):
        draft_additive_schema(gap, repo, binding=binding)


def test_forged_source_and_tampered_base_are_rejected(workspace):
    from procurement_ontology.schema_draft import detect_gap, draft_additive_schema
    _, draft, binding, source, span = workspace
    proposal = {"operation": "add_relation", "name": "supports_remote_deployment", "description": "远程部署"}
    with pytest.raises(ValueError):
        detect_gap(binding, span.model_copy(update={"quote": "伪造"}), proposal, source=source)
    gap = detect_gap(binding, span, proposal, source=source)
    target = draft / binding.yaml_path.relative_to(workspace[0])
    target.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="摘要"):
        draft_additive_schema(gap, draft, binding=binding)


def test_model_proposal_creates_scoped_review_record(workspace):
    from procurement_ontology.identity import Identity
    from procurement_ontology.schema_draft import SchemaDraftService
    repo, draft, binding, source, span = workspace

    class Records:
        def append_schema_draft(self, scope, record):
            self.scope, self.record = scope, record

    class Client:
        def complete(self, prompt, show_prompt=False):
            return '{"operation":"add_relation","name":"supports_remote_deployment","description":"远程部署"}'

    records = Records()
    from procurement_ontology.maintenance import WriteGate
    records.gate = WriteGate()
    service = SchemaDraftService(records, draft.parent / "generated", client_factory=lambda binding: Client())
    result = service.from_suggestion(Identity("buyer", "test_buyer1", "company_admin"), binding, source,
                                     {"proposed_relation": "远程部署", "source_spans": [span.model_dump()]})
    assert result["status"] == "DRAFT"
    assert records.scope == "test_buyer1"
    assert records.record["gap"]["source_span"]["quote"] == source.text
    assert records.record["artifacts"]["version"] == "v2"
    assert git(repo, "status", "--porcelain") == ""
    with pytest.raises(PermissionError):
        service.from_suggestion(Identity("supplier", "test_supplier1", "company_admin"), binding, source,
                                {"source_spans": [span.model_dump()]})
