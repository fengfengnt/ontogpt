"""Export only committed application inputs, excluding private runtime and host Git."""

import io
from pathlib import Path
import subprocess
import sys
import tarfile


def included(name):
    exact = {"pyproject.toml", "README.md", ".gitignore", "frontend/procurement-ontology/package.json",
             "frontend/procurement-ontology/package-lock.json", "frontend/procurement-ontology/index.html",
             "frontend/procurement-ontology/tsconfig.json", "frontend/procurement-ontology/vite.config.ts",
             "services/procurement_ontology/pyproject.toml", "services/procurement_ontology/uv.lock",
             "services/procurement_ontology/schema_registry.yaml"}
    return name in exact or name.startswith(("src/ontogpt/", "services/procurement_ontology/procurement_ontology/",
                                            "frontend/procurement-ontology/src/"))


def prepare(root, destination):
    destination.mkdir(parents=True, exist_ok=False)
    archive = subprocess.check_output(["git", "-C", str(root), "archive", "HEAD"])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            name = member.name
            if included(name):
                output = destination / "seed" / name
            elif name in {"deploy/ontology/Dockerfile", "deploy/ontology/entrypoint.py"}:
                output = destination / Path(name).name
            else:
                continue
            if not output.resolve().is_relative_to(destination.resolve()):
                raise ValueError("Invalid archive path")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(tar.extractfile(member).read())
    release = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    (destination / "release.txt").write_text(release + "\n", encoding="utf-8")
    return release


if __name__ == "__main__":
    print(prepare(Path(__file__).resolve().parents[2], Path(sys.argv[1]).resolve()))
