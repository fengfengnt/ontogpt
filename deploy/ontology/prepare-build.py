"""Export allowlisted application inputs and identify the actual working content."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def included(name):
    exact = {"VERSION", "pyproject.toml", "README.md", ".gitignore", "frontend/procurement-ontology/package.json",
             "frontend/procurement-ontology/package-lock.json", "frontend/procurement-ontology/index.html",
             "frontend/procurement-ontology/tsconfig.json", "frontend/procurement-ontology/vite.config.ts",
             "services/procurement_ontology/pyproject.toml", "services/procurement_ontology/uv.lock",
             "services/procurement_ontology/schema_registry.yaml"}
    return name in exact or name.startswith(("src/ontogpt/", "services/procurement_ontology/procurement_ontology/",
                                            "frontend/procurement-ontology/src/"))


def prepare(root, destination):
    version = (root / "VERSION").read_text(encoding="utf-8-sig").strip()
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise ValueError("VERSION must contain MAJOR.MINOR.PATCH")
    tracked = subprocess.check_output(["git", "-C", str(root), "ls-files", "-z"]).decode().split("\0")
    required = {"VERSION", "deploy/ontology/Dockerfile", "deploy/ontology/entrypoint.py"}
    names = sorted({name for name in tracked if name and included(name)} | required)
    destination.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name in names:
        source = root / name
        if source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
            raise ValueError("Unsafe build input: " + name)
        data = source.read_bytes()
        if name == "VERSION":
            data = (version + "\n").encode()
        output = destination / ("seed/" + name if included(name) else Path(name).name)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    revision = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    source = {"revision": revision, "version": version, "inputs": hashes}
    release = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()[:40]
    (destination / "seed/.build-source.json").write_text(json.dumps(source, sort_keys=True), encoding="utf-8")
    (destination / "release.txt").write_text(release + "\n", encoding="utf-8")
    (destination / "revision.txt").write_text(revision + "\n", encoding="utf-8")
    (destination / "VERSION").write_text(version + "\n", encoding="utf-8")
    return release


if __name__ == "__main__":
    print(prepare(Path(__file__).resolve().parents[2], Path(sys.argv[1]).resolve()))
