import runpy
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]


def test_release_survives_recreation_and_isolates_upgrade(tmp_path):
    module = runpy.run_path(str(ROOT / "deploy/ontology/entrypoint.py"))
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "source.py").write_text("original", encoding="utf-8")
    module["write_manifest"](seed, "a" * 40)
    workspace = tmp_path / "workspace"
    first = module["initialize_release"](seed, workspace)
    draft = workspace / "drafts" / "synthetic"
    draft.parent.mkdir()
    subprocess.run(["git", "-C", str(first), "worktree", "add", "-b", "codex/schema-draft/synthetic", str(draft)], check=True, capture_output=True)
    (draft / "draft.yaml").write_text("synthetic", encoding="utf-8")
    assert module["initialize_release"](seed, workspace) == first
    assert (draft / "draft.yaml").read_text() == "synthetic"
    module["write_manifest"](seed, "b" * 40)
    second = module["initialize_release"](seed, workspace)
    assert second != first and (first / ".git").is_dir()
    (second / "source.py").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        module["initialize_release"](seed, workspace)


def test_tampered_seed_fails_before_initializing(tmp_path):
    module = runpy.run_path(str(ROOT / "deploy/ontology/entrypoint.py"))
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "source.py").write_text("original", encoding="utf-8")
    module["write_manifest"](seed, "a" * 40)
    (seed / "source.py").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        module["initialize_release"](seed, tmp_path / "workspace")


def test_build_context_excludes_runtime_and_uncommitted_files(tmp_path):
    module = runpy.run_path(str(ROOT / "deploy/ontology/prepare-build.py"))
    assert module["included"]("src/ontogpt/templates/company/test/v1/schema.yaml")
    assert not module["included"]("services/procurement_ontology/runtime/.env")
    assert not module["included"](".git/config")
    assert not module["included"]("frontend/procurement-ontology/node_modules/synthetic.js")
    assert module["included"]("services/procurement_ontology/uv.lock")
