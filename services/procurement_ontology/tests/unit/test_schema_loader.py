"""Enterprise schemas must load without generation or modifying template files."""

import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[4]
TEMPLATES = ROOT / "src/ontogpt/templates"
REGISTRY = ROOT / "services/procurement_ontology/schema_registry.yaml"


def test_buyer_supplier_have_distinct_files():
    from procurement_ontology.schema_loader import load_registered_template

    buyer = load_registered_template("test_buyer1", "computer", "v1")
    supplier = load_registered_template("test_supplier1", "computer", "v1")
    assert buyer.yaml_path != supplier.yaml_path
    assert buyer.python_path != supplier.python_path
    assert buyer.root_class == "BuyerComputerExtraction"
    assert supplier.root_class == "SupplierComputerExtraction"
    assert "collection_fields" in buyer.python_class.model_fields
    assert "cost_items" in supplier.python_class.model_fields
    assert "cost_items" not in buyer.python_class.model_fields


def test_nested_import_and_hash():
    from procurement_ontology.schema_loader import load_registered_template

    files_before = {path: path.read_bytes() for path in (TEMPLATES / "company").rglob("*.yaml")}
    binding = load_registered_template("test_buyer1", "computer", "v1")
    assert binding.schema_view.get_class(binding.root_class).tree_root
    assert binding.template_details[2] is binding.python_class
    assert binding.python_class.model_validate({}).model_dump() is not None
    assert all(path.read_bytes() == content for path, content in files_before.items())
    assert not (TEMPLATES / "test_buyer1_computer.yaml").exists()


def test_tampered_or_escaped_schema_is_rejected(tmp_path):
    from procurement_ontology.schema_loader import load_registered_template

    shutil.copytree(TEMPLATES / "company", tmp_path / "company")
    target = tmp_path / "company/test_buyer1/computer/v1/test_buyer1_computer.yaml"
    target.write_text(target.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        load_registered_template("test_buyer1", "computer", "v1", template_root=tmp_path)
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    registry["schemas"][0]["yaml_path"] = "../../untrusted.yaml"
    custom_registry = tmp_path / "registry.yaml"
    custom_registry.write_text(yaml.safe_dump(registry), encoding="utf-8")
    with pytest.raises(ValueError, match="path"):
        load_registered_template("test_buyer1", "computer", "v1", registry_path=custom_registry, template_root=tmp_path)


def test_unknown_company_has_no_default_schema():
    from procurement_ontology.schema_loader import load_registered_template

    with pytest.raises(ValueError):
        load_registered_template("other_company", "computer", "v1")


def test_imported_type_schema_checksum_is_checked(tmp_path):
    from procurement_ontology.schema_loader import load_registered_template

    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    registry["schemas"][0]["type_schema_sha256"] = "0" * 64
    custom_registry = tmp_path / "registry.yaml"
    custom_registry.write_text(yaml.safe_dump(registry), encoding="utf-8")
    with pytest.raises(ValueError, match="dependency"):
        load_registered_template("test_buyer1", "computer", "v1", registry_path=custom_registry)


def test_installed_template_artifacts(tmp_path):
    from procurement_ontology.schema_loader import load_registered_template

    load_registered_template("test_buyer1", "computer", "v1")
    result = subprocess.run(["uv", "build", "--wheel", "--out-dir", str(tmp_path / "dist")],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-1500:]
    wheel = next((tmp_path / "dist").glob("*.whl"))
    extracted = tmp_path / "installed"
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert "ontogpt/templates/company/test_buyer1/computer/v1/test_buyer1_computer.yaml" in names
        assert "ontogpt/templates/company/test_supplier1/computer/v1/test_supplier1_computer.py" in names
        archive.extractall(extracted)
    program = """
import sys
sys.path.insert(0, sys.argv[1])
import ontogpt
assert ontogpt.__file__.startswith(sys.argv[1])
from procurement_ontology.schema_loader import load_registered_template
for company in ('test_buyer1', 'test_supplier1'):
    binding = load_registered_template(company, 'computer', 'v1')
    assert str(binding.yaml_path).startswith(sys.argv[1])
    binding.python_class.model_validate({})
print('installed enterprise templates load')
"""
    check = subprocess.run([sys.executable, "-c", program, str(extracted)],
                           capture_output=True, text=True, env=os.environ.copy())
    assert check.returncode == 0, check.stderr[-1500:]
    assert "installed enterprise templates load" in check.stdout
