"""SQLite authentication and explicit platform/company authorization."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str = field(repr=False)

    def __post_init__(self):
        if not self.username or len(self.username) > 128 or self.username != self.username.strip():
            raise ValueError("用户名无效")
        if not 12 <= len(self.password) <= 1024:
            raise ValueError("密码长度须为 12 到 1024 个字符")


@dataclass(frozen=True)
class Identity:
    account_id: str
    scope_id: str
    role: str


PERMISSIONS = {
    "platform_admin": {"read", "write", "review", "publish", "provision"},
    "company_admin": {"read", "write", "review", "publish", "activate_schema", "manage_accounts"},
    "reader": {"read"},
}


def authorize(identity: Identity, scope_id: str, action: str) -> None:
    if identity.scope_id != scope_id or action not in PERMISSIONS.get(identity.role, set()):
        raise PermissionError("当前身份无权执行此操作")
    if (identity.role == "platform_admin") != (scope_id == "platform"):
        raise PermissionError("当前身份无权执行此操作")


def _password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def _password_matches(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, expected = encoded.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=32)
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class IdentityStore:
    def __init__(self, sqlite_path: str | Path):
        self.path = Path(sqlite_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS companies (
                    company_id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'PROVISIONING',
                    created_by TEXT NOT NULL, created_at REAL NOT NULL,
                    CHECK (status IN ('PROVISIONING','READY','FAILED'))
                );
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL, role TEXT NOT NULL,
                    company_id TEXT REFERENCES companies(company_id), active INTEGER NOT NULL DEFAULT 1,
                    CHECK ((role = 'platform_admin' AND company_id IS NULL) OR
                           (role IN ('company_admin','reader') AND company_id IS NOT NULL))
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(account_id),
                    expires_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS service_tokens (
                    token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(account_id),
                    expires_at REAL NOT NULL
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

    def bootstrap_admin(self, credentials: Credentials) -> Identity:
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM accounts WHERE role = 'platform_admin'").fetchone():
                raise ValueError("平台管理员已初始化")
            account_id = uuid.uuid4().hex
            db.execute("INSERT INTO accounts (account_id, username, password_hash, role) VALUES (?,?,?,?)",
                       (account_id, credentials.username, _password_hash(credentials.password), "platform_admin"))
        return Identity(account_id, "platform", "platform_admin")

    def create_company(self, company_id: str, actor: Identity) -> None:
        authorize(actor, "platform", "provision")
        if company_id == "platform" or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,63}", company_id):
            raise ValueError("企业标识无效")
        with self._db() as db:
            db.execute("INSERT OR IGNORE INTO companies (company_id, created_by, created_at) VALUES (?,?,?)",
                       (company_id, actor.account_id, time.time()))

    def mark_company_ready(self, company_id: str, actor: Identity) -> None:
        authorize(actor, "platform", "provision")
        with self._db() as db:
            if db.execute("UPDATE companies SET status='READY' WHERE company_id=?", (company_id,)).rowcount != 1:
                raise ValueError("企业尚未开通")

    def company_state(self, company_id: str, actor: Identity) -> dict | None:
        authorize(actor, "platform", "provision")
        with self._db() as db:
            row = db.execute("SELECT company_id,status FROM companies WHERE company_id=?", (company_id,)).fetchone()
            return dict(row) if row else None

    def company_has_account(self, company_id: str, actor: Identity) -> bool:
        authorize(actor, "platform", "provision")
        with self._db() as db:
            return db.execute("SELECT 1 FROM accounts WHERE company_id=?", (company_id,)).fetchone() is not None

    def ready_company_ids(self) -> list[str]:
        with self._db() as db:
            return [row[0] for row in db.execute("SELECT company_id FROM companies WHERE status='READY'")]

    def create_account(self, company_id: str, role: str, credentials: Credentials, actor: Identity) -> Identity:
        if role not in {"company_admin", "reader"}:
            raise PermissionError("不允许创建此类账号")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            company = db.execute("SELECT status FROM companies WHERE company_id=?", (company_id,)).fetchone()
            if not company:
                raise ValueError("企业尚未开通")
            if actor.role == "platform_admin":
                authorize(actor, "platform", "provision")
                if company["status"] != "PROVISIONING" or role != "company_admin" or db.execute(
                    "SELECT 1 FROM accounts WHERE company_id=?", (company_id,),
                ).fetchone():
                    raise PermissionError("平台只能在企业初始化时创建首个管理员")
            else:
                authorize(actor, company_id, "manage_accounts")
            account_id = uuid.uuid4().hex
            db.execute("INSERT INTO accounts (account_id, username, password_hash, role, company_id) VALUES (?,?,?,?,?)",
                       (account_id, credentials.username, _password_hash(credentials.password), role, company_id))
        return Identity(account_id, company_id, role)

    @staticmethod
    def _identity(db, account_id: str) -> Identity:
        row = db.execute("SELECT * FROM accounts WHERE account_id=? AND active=1", (account_id,)).fetchone()
        if not row:
            raise PermissionError("认证失败或会话已失效")
        if row["company_id"] is not None:
            company = db.execute("SELECT status FROM companies WHERE company_id=?", (row["company_id"],)).fetchone()
            if not company or company["status"] != "READY":
                raise PermissionError("认证失败或企业尚未就绪")
        return Identity(row["account_id"], row["company_id"] or "platform", row["role"])

    def authenticate(self, credentials: Credentials) -> Identity:
        with self._db() as db:
            row = db.execute("SELECT account_id,password_hash FROM accounts WHERE username=?", (credentials.username,)).fetchone()
            if not row or not _password_matches(credentials.password, row["password_hash"]):
                raise PermissionError("认证失败")
            return self._identity(db, row["account_id"])

    def _issue_token(self, identity: Identity, table: str, lifetime: int) -> str:
        token = secrets.token_urlsafe(32)
        with self._db() as db:
            if self._identity(db, identity.account_id) != identity:
                raise PermissionError("身份信息已变化")
            db.execute(f"INSERT INTO {table} (token_hash,account_id,expires_at) VALUES (?,?,?)",
                       (_token_hash(token), identity.account_id, time.time() + lifetime))
        return token

    def _authenticate_token(self, token: str, table: str) -> Identity:
        with self._db() as db:
            row = db.execute(f"SELECT account_id FROM {table} WHERE token_hash=? AND expires_at>?",
                             (_token_hash(token), time.time())).fetchone()
            if not row:
                raise PermissionError("认证失败或会话已失效")
            return self._identity(db, row["account_id"])

    def issue_session(self, identity: Identity) -> str:
        return self._issue_token(identity, "sessions", 3600)

    def authenticate_token(self, token: str) -> Identity:
        return self._authenticate_token(token, "sessions")

    def revoke_session(self, token: str) -> None:
        with self._db() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (_token_hash(token),))

    def issue_service_token(self, identity: Identity) -> str:
        if identity.scope_id == "platform":
            raise PermissionError("MCP 服务令牌须绑定企业")
        return self._issue_token(identity, "service_tokens", 86400)

    def authenticate_service_token(self, token: str) -> Identity:
        return self._authenticate_token(token, "service_tokens")
