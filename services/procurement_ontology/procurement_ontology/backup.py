"""Consistent maintenance-window backup; restore only into an empty target."""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal

import yaml
from rdflib import Dataset
from rdflib.compare import isomorphic

from .models import DomainModel, utc_now


class BackupFile(DomainModel):
    file: str
    sha256: str


class DatasetBackup(BackupFile):
    scope_id: str
    quads: int
    versions: dict[str, str | None]


class BackupManifest(DomainModel):
    format_version: Literal[1] = 1
    created_at: str
    source_dataset_prefix: str
    sqlite: BackupFile
    datasets: list[DatasetBackup]
    schema_registry: dict


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _dataset(content):
    dataset = Dataset()
    dataset.parse(data=content, format="nquads")
    return dataset


class BackupManager:
    def __init__(self, store, identities, catalog):
        if store.gate is not identities.gate or store.gate is not catalog.gate:
            raise ValueError("备份要求持久层共享同一维护窗口")
        self.store, self.identities, self.catalog = store, identities, catalog
        self.gate = store.gate

    def _export_dataset(self, scope):
        response = self.store.session.get(f"{self.store.base_url}/{self.store.dataset_name(scope)}",
                                          headers={"Accept": "application/n-quads"}, timeout=60)
        response.raise_for_status()
        return response.content

    def backup_service(self, destination) -> BackupManifest:
        destination = Path(destination).resolve()
        with self.gate.maintenance():
            scopes = self.store.list_dataset_scopes()
            with closing(sqlite3.connect(self.identities.path)) as db:
                required = {row[0] for row in db.execute("SELECT company_id FROM companies WHERE status='READY'")}
            if "platform" not in scopes or not required.issubset(scopes):
                raise ValueError("平台或已开通企业数据集不完整，不能生成完整备份")
            destination.mkdir(parents=True, exist_ok=False)
            (destination / "rdf").mkdir()
            sqlite_path = destination / "control.sqlite3"
            with closing(sqlite3.connect(self.identities.path)) as source, closing(sqlite3.connect(sqlite_path)) as target:
                source.backup(target)
            records = []
            for scope in scopes:
                content = self._export_dataset(scope)
                dataset = _dataset(content)
                filename = "rdf/" + scope + ".nq"
                path = destination / filename
                path.write_bytes(content)
                versions = {}
                for kind in ("tree", "ontology"):
                    current = self.store.read_current(scope, kind)
                    versions[kind] = current.id if current else None
                records.append(DatasetBackup(scope_id=scope, file=filename, sha256=_digest(path),
                                             quads=sum(1 for _ in dataset.quads()), versions=versions))
            manifest = BackupManifest(created_at=utc_now().isoformat(), source_dataset_prefix=self.store.dataset_prefix,
                                      sqlite=BackupFile(file="control.sqlite3", sha256=_digest(sqlite_path)), datasets=records,
                                      schema_registry=yaml.safe_load(self.catalog.registry_path.read_text(encoding="utf-8")))
            temporary = destination / "manifest.json.tmp"
            temporary.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(destination / "manifest.json")
            return manifest

    @staticmethod
    def _checked_file(root, record, expected_name):
        path = (root / record.file).resolve()
        if record.file != expected_name or not path.is_relative_to(root) or not path.is_file():
            raise ValueError("备份文件缺失或路径不合法")
        if _digest(path) != record.sha256:
            raise ValueError("备份文件摘要不匹配")
        return path

    def restore_service(self, manifest_path) -> None:
        manifest_path = Path(manifest_path).resolve()
        root = manifest_path.parent
        manifest = BackupManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        if (self.store.dataset_prefix.startswith(manifest.source_dataset_prefix)
                or manifest.source_dataset_prefix.startswith(self.store.dataset_prefix)):
            raise ValueError("恢复前缀不能与备份源前缀相同或互为前缀，请使用独立前缀")
        sqlite_path = self._checked_file(root, manifest.sqlite, "control.sqlite3")
        records = {record.scope_id: record for record in manifest.datasets}
        if len(records) != len(manifest.datasets) or "platform" not in records:
            raise ValueError("备份数据域清单不完整")
        contents = {}
        for scope, record in records.items():
            self.store.dataset_name(scope)
            path = self._checked_file(root, record, "rdf/" + scope + ".nq")
            contents[scope] = path.read_bytes()
            if sum(1 for _ in _dataset(contents[scope]).quads()) != record.quads:
                raise ValueError("备份四元组数量不一致")
        with closing(sqlite3.connect(sqlite_path)) as source:
            if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or source.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("SQLite 完整性校验失败")
            required = {row[0] for row in source.execute("SELECT company_id FROM companies WHERE status='READY'")}
            if not required.issubset(records):
                raise ValueError("备份缺少企业数据集")
            for company, category, version, yaml_sha, python_sha in source.execute(
                    "SELECT company_id,category_key,version,yaml_sha256,python_sha256 FROM active_schemas"):
                binding = self.catalog._load(company, category, version)
                if (binding.yaml_sha256, binding.python_sha256) != (yaml_sha, python_sha):
                    raise ValueError("目标尚未部署恢复所需的 schema 产物")
        with self.gate.maintenance():
            with closing(sqlite3.connect(self.identities.path)) as target:
                occupied = target.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] + target.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
            if occupied or self.store.list_dataset_scopes():
                raise ValueError("恢复目标必须为空，禁止覆盖现有服务数据")
            marker = self.identities.path.parent / "restore.incomplete"
            marker.write_text(manifest_path.name, encoding="utf-8")
            for scope, content in contents.items():
                self.store.ensure_dataset(scope)
                response = self.store.session.post(f"{self.store.base_url}/{self.store.dataset_name(scope)}", data=content,
                                                   headers={"Content-Type": "application/n-quads"}, timeout=60)
                response.raise_for_status()
                expected, actual = _dataset(content), _dataset(self._export_dataset(scope))
                expected_graphs = {graph.identifier: graph for graph in expected.graphs()}
                actual_graphs = {graph.identifier: graph for graph in actual.graphs()}
                if expected_graphs.keys() != actual_graphs.keys() or any(not isomorphic(graph, actual_graphs[key]) for key, graph in expected_graphs.items()):
                    raise ValueError("恢复后的 RDF 图与备份不一致")
                for kind, identifier in records[scope].versions.items():
                    snapshot = self.store.read_current(scope, kind)
                    if (snapshot.id if snapshot else None) != identifier:
                        raise ValueError("恢复后的当前指针不一致")
            with closing(sqlite3.connect(sqlite_path)) as source, closing(sqlite3.connect(self.identities.path)) as target:
                source.backup(target)
            (self.identities.path.parent / "restore.complete.json").write_text(
                json.dumps({"restored_at": utc_now().isoformat(), "dataset_prefix": self.store.dataset_prefix,
                            "manifest_sha256": _digest(manifest_path)}, indent=2), encoding="utf-8")
            marker.unlink()
