"""Load only registered, pre-generated company schemas without writing files."""

from __future__ import annotations

import hashlib
import importlib.metadata
import sys
import types
from dataclasses import dataclass
from pathlib import Path

import ontogpt
import linkml_runtime
import yaml
from linkml_runtime import SchemaView

DEFAULT_REGISTRY = Path(__file__).resolve().parents[1] / "schema_registry.yaml"


@dataclass(frozen=True)
class TemplateBinding:
    company_id: str
    category_key: str
    version: str
    yaml_path: Path
    python_path: Path
    yaml_sha256: str
    python_sha256: str
    root_class: str
    generator_version: str
    module: types.ModuleType
    python_class: type
    schema_view: SchemaView

    @property
    def template_details(self):
        return (self.schema_view.get_class(self.root_class), self.module, self.python_class, self.schema_view)


def _registered_path(root: Path, relative: str, key: tuple[str, str, str]) -> Path:
    prefix = (root / "company" / key[0] / key[1] / key[2]).resolve()
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(prefix):
        raise ValueError("Registered template path escapes company/version directory")
    return path


def load_registered_template(
    company_id: str, category_key: str, version: str, *,
    registry_path: Path = DEFAULT_REGISTRY, template_root: Path | None = None,
) -> TemplateBinding:
    registry = yaml.safe_load(Path(registry_path).read_text(encoding="utf-8"))
    key = (company_id, category_key, version)
    matches = [entry for entry in registry.get("schemas", [])
               if (entry["company_id"], entry["category_key"], entry["version"]) == key]
    if len(matches) != 1:
        raise ValueError("Schema version is not uniquely registered")
    entry = matches[0]
    root = template_root or Path(ontogpt.__file__).resolve().parent / "templates"
    yaml_path = _registered_path(root, entry["yaml_path"], key)
    python_path = _registered_path(root, entry["python_path"], key)
    for path, field in ((yaml_path, "yaml_sha256"), (python_path, "python_sha256")):
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry[field]:
            raise ValueError("Registered template checksum does not match deployed artifact")
    for dependency, expected in entry["dependency_versions"].items():
        if importlib.metadata.version(dependency) != expected:
            raise ValueError("Registered template dependency version does not match deployment")
    type_schema = Path(linkml_runtime.__file__).resolve().parent / "linkml_model/model/schema/types.yaml"
    if hashlib.sha256(type_schema.read_bytes()).hexdigest() != entry["type_schema_sha256"]:
        raise ValueError("Registered template dependency checksum does not match deployment")
    view = SchemaView(str(yaml_path), importmap={"linkml:types": str(type_schema)})
    roots = [cls.name for cls in view.all_classes().values() if cls.tree_root]
    if roots != [entry["root_class"]]:
        raise ValueError("Registered root class does not match LinkML schema")
    name = "_procurement_" + "_".join(key) + "_" + entry["python_sha256"]
    module = types.ModuleType(name)
    module.__file__ = str(python_path)
    sys.modules[name] = module
    try:
        exec(compile(python_path.read_text(encoding="utf-8"), str(python_path), "exec"), module.__dict__)
        python_class = getattr(module, entry["root_class"])
    except Exception:
        sys.modules.pop(name, None)
        raise
    return TemplateBinding(
        company_id, category_key, version, yaml_path, python_path,
        entry["yaml_sha256"], entry["python_sha256"], entry["root_class"],
        entry["generator_version"], module, python_class, view,
    )
