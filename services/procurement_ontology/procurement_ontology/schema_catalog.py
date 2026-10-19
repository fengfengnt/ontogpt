"""Transactional active schema pointers; deployed registry is not an active pointer."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .identity import Identity, authorize
from .models import utc_now
from .schema_loader import DEFAULT_REGISTRY, TemplateBinding, load_registered_template


@dataclass(frozen=True)
class ActivationRecord:
    audit_id: str
    company_id: str
    category_key: str
    version: str
    previous_version: str | None
    yaml_sha256: str
    python_sha256: str
    actor_id: str
    activated_at: str


class SchemaCatalog:
    def __init__(self, sqlite_path: str | Path, *, registry_path: Path = DEFAULT_REGISTRY,
                 template_root: Path | None = None):
        self.path = Path(sqlite_path)
        self.registry_path = Path(registry_path)
        self.template_root = template_root
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS active_schemas (
                    company_id TEXT NOT NULL REFERENCES companies(company_id),
                    category_key TEXT NOT NULL, version TEXT NOT NULL,
                    yaml_sha256 TEXT NOT NULL, python_sha256 TEXT NOT NULL,
                    actor_id TEXT NOT NULL REFERENCES accounts(account_id), activated_at TEXT NOT NULL,
                    PRIMARY KEY (company_id, category_key)
                );
                CREATE TABLE IF NOT EXISTS schema_activation_audit (
                    audit_id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(company_id),
                    category_key TEXT NOT NULL, version TEXT NOT NULL, previous_version TEXT,
                    yaml_sha256 TEXT NOT NULL, python_sha256 TEXT NOT NULL,
                    actor_id TEXT NOT NULL REFERENCES accounts(account_id), activated_at TEXT NOT NULL
                );
            """)

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def _load(self, company_id: str, category_key: str, version: str) -> TemplateBinding:
        return load_registered_template(company_id, category_key, version,
                                        registry_path=self.registry_path, template_root=self.template_root)

    def active(self, company_id: str, category_key: str) -> TemplateBinding:
        with self._db() as db:
            row = db.execute("SELECT * FROM active_schemas WHERE company_id=? AND category_key=?",
                             (company_id, category_key)).fetchone()
        if not row:
            raise ValueError("企业品类尚未启用 schema")
        binding = self._load(company_id, category_key, row["version"])
        if binding.yaml_sha256 != row["yaml_sha256"] or binding.python_sha256 != row["python_sha256"]:
            raise ValueError("Active schema checksum does not match activated artifacts")
        return binding

    def activate_schema(self, identity: Identity, company_id: str,
                        category_key: str, version: str) -> ActivationRecord:
        authorize(identity, company_id, "activate_schema")
        binding = self._load(company_id, category_key, version)
        audit_id, timestamp = uuid.uuid4().hex, utc_now().isoformat()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT version FROM active_schemas WHERE company_id=? AND category_key=?",
                                  (company_id, category_key)).fetchone()
            previous_version = previous["version"] if previous else None
            values = (company_id, category_key, version, binding.yaml_sha256,
                      binding.python_sha256, identity.account_id, timestamp)
            db.execute("""
                INSERT INTO active_schemas (company_id,category_key,version,yaml_sha256,python_sha256,actor_id,activated_at)
                VALUES (?,?,?,?,?,?,?) ON CONFLICT(company_id,category_key) DO UPDATE SET
                  version=excluded.version, yaml_sha256=excluded.yaml_sha256, python_sha256=excluded.python_sha256,
                  actor_id=excluded.actor_id, activated_at=excluded.activated_at
            """, values)
            db.execute("""
                INSERT INTO schema_activation_audit
                  (audit_id,company_id,category_key,version,previous_version,yaml_sha256,python_sha256,actor_id,activated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (audit_id, company_id, category_key, version, previous_version,
                  binding.yaml_sha256, binding.python_sha256, identity.account_id, timestamp))
        return ActivationRecord(audit_id, company_id, category_key, version, previous_version,
                                binding.yaml_sha256, binding.python_sha256, identity.account_id, timestamp)
