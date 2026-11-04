"""Initialize a release-specific Git workspace; never overwrite a previous release."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from filelock import FileLock


def write_manifest(seed, release):
    files = {str(path.relative_to(seed)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(seed.rglob("*")) if path.is_file() and path.name != ".release.json"
             and ".git" not in path.parts and "__pycache__" not in path.parts}
    (seed / ".release.json").write_text(json.dumps({"release": release, "files": files}, sort_keys=True), encoding="utf-8")


def verify(root, manifest):
    for name, checksum in manifest["files"].items():
        path = root / name
        if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
            raise ValueError("Unsafe release path")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
            raise ValueError("Release checksum mismatch: " + name)


def initialize_release(seed, workspace):
    manifest = json.loads((seed / ".release.json").read_text(encoding="utf-8"))
    release_id = manifest["release"]
    if not re.fullmatch(r"[a-f0-9]{40}", release_id):
        raise ValueError("Release must be a full source commit")
    verify(seed, manifest)
    releases = workspace / "releases"
    releases.mkdir(parents=True, exist_ok=True)
    release = releases / release_id
    with FileLock(workspace / "initialize.lock"):
        if not release.exists():
            temporary = Path(tempfile.mkdtemp(prefix=".initializing-", dir=releases))
            shutil.copytree(seed, temporary, dirs_exist_ok=True)
            for args in (["init", "-b", "main"], ["config", "user.name", "Ontology schema drafts"],
                         ["config", "user.email", "ontology@localhost"], ["add", "."],
                         ["commit", "-m", "Image release " + release_id]):
                subprocess.run(["git", "-C", str(temporary), *args], check=True, capture_output=True)
            temporary.rename(release)
        if json.loads((release / ".release.json").read_text(encoding="utf-8")) != manifest:
            raise ValueError("Release identity reused for different image content")
        verify(release, manifest)
        if not (release / ".git").is_dir():
            raise ValueError("Release Git metadata is missing")
    return release


if __name__ == "__main__":
    seed = Path("/opt/ontology-seed")
    if len(sys.argv) == 3 and sys.argv[1] == "--write-manifest":
        write_manifest(seed, sys.argv[2])
    else:
        release = initialize_release(seed, Path("/workspace"))
        os.environ["PYTHONPATH"] = str(release / "services/procurement_ontology") + os.pathsep + str(release / "src")
        os.chdir(release)
        os.execv(sys.executable, [sys.executable, "-m", "procurement_ontology.runtime", *sys.argv[1:]])
