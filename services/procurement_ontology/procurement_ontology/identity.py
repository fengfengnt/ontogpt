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

from .maintenance import WriteGate
from .store import VersionConflict


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
    def __init__(self, sqlite_path: str | Path, *, gate=None):
        self.gate = gate or WriteGate()
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
                CREATE TABLE IF NOT EXISTS sso_users (
                    id TEXT PRIMARY KEY, issuer TEXT NOT NULL, subject TEXT NOT NULL,
                    preferred_username TEXT NOT NULL, account_id TEXT UNIQUE REFERENCES accounts(account_id),
                    created_at REAL NOT NULL, UNIQUE (issuer, subject)
                );
                CREATE TABLE IF NOT EXISTS sso_pending_sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES sso_users(id),
                    expires_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sso_assignment_audit (
                    user_id TEXT PRIMARY KEY REFERENCES sso_users(id),
                    account_id TEXT NOT NULL REFERENCES accounts(account_id),
                    company_id TEXT NOT NULL REFERENCES companies(company_id),
                    assigned_by TEXT NOT NULL REFERENCES accounts(account_id), assigned_at REAL NOT NULL
                );
            """)

    @contextmanager
    def _db(self):
        with self.gate.writer():
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

    def sso_user(self, issuer: str, sub: str, username: str) -> dict:
        if not issuer or not sub or len(sub) > 255 or len(username) > 128:
            raise ValueError("SSO 身份无效")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO sso_users (id,issuer,subject,preferred_username,created_at) VALUES (?,?,?,?,?) "
                       "ON CONFLICT(issuer,subject) DO UPDATE SET preferred_username=excluded.preferred_username",
                       (uuid.uuid4().hex, issuer, sub, username, time.time()))
            return dict(db.execute("SELECT * FROM sso_users WHERE issuer=? AND subject=?", (issuer, sub)).fetchone())

    def sso_actor(self, user_id: str) -> Identity | None:
        with self._db() as db:
            user = db.execute("SELECT account_id FROM sso_users WHERE id=?", (user_id,)).fetchone()
            if not user:
                raise KeyError(user_id)
            return self._identity(db, user["account_id"]) if user["account_id"] else None

    def list_sso_users(self, actor: Identity) -> list[dict]:
        authorize(actor, "platform", "provision")
        with self._db() as db:
            return [dict(row) for row in db.execute(
                "SELECT u.*,a.company_id FROM sso_users u LEFT JOIN accounts a ON a.account_id=u.account_id "
                "ORDER BY u.created_at,u.id")]

    def assign_sso_user(self, user_id: str, company_id: str, actor: Identity) -> Identity:
        authorize(actor, "platform", "provision")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            company = db.execute("SELECT status FROM companies WHERE company_id=?", (company_id,)).fetchone()
            if not company or company["status"] != "READY":
                raise ValueError("仅可分配到已就绪企业")
            user = db.execute("SELECT account_id FROM sso_users WHERE id=?", (user_id,)).fetchone()
            if not user:
                raise KeyError(user_id)
            if user["account_id"]:
                identity = self._identity(db, user["account_id"])
                if identity.scope_id != company_id:
                    raise VersionConflict("该用户已经分配企业")
                return identity
            account_id = uuid.uuid4().hex
            db.execute("INSERT INTO accounts (account_id,username,password_hash,role,company_id) VALUES (?,?,?,?,?)",
                       (account_id, "sso_" + account_id, "!sso-only", "company_admin", company_id))
            db.execute("UPDATE sso_users SET account_id=? WHERE id=?", (account_id, user_id))
            db.execute("INSERT INTO sso_assignment_audit VALUES (?,?,?,?,?)",
                       (user_id, account_id, company_id, actor.account_id, time.time()))
            return self._identity(db, account_id)

    def issue_pending_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        with self._db() as db:
            db.execute("DELETE FROM sso_pending_sessions WHERE expires_at<=?", (time.time(),))
            db.execute("INSERT INTO sso_pending_sessions VALUES (?,?,?)", (_token_hash(token), user_id, time.time() + 3600))
        return token

    def pending_user(self, token: str) -> dict:
        with self._db() as db:
            row = db.execute("SELECT u.* FROM sso_pending_sessions p JOIN sso_users u ON u.id=p.user_id "
                             "WHERE p.token_hash=? AND p.expires_at>?", (_token_hash(token), time.time())).fetchone()
            if not row:
                raise PermissionError("待分配会话已失效")
            return dict(row)

    def activate_pending(self, token: str) -> Identity:
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT u.account_id FROM sso_pending_sessions p JOIN sso_users u ON u.id=p.user_id "
                             "WHERE p.token_hash=? AND p.expires_at>?", (_token_hash(token), time.time())).fetchone()
            if not row:
                raise PermissionError("待分配会话已失效")
            if not row["account_id"]:
                raise VersionConflict("尚未分配企业，请等待超级管理员处理")
            actor = self._identity(db, row["account_id"])
            db.execute("DELETE FROM sso_pending_sessions WHERE token_hash=?", (_token_hash(token),))
            return actor

    def revoke_pending_session(self, token: str) -> None:
        with self._db() as db:
            db.execute("DELETE FROM sso_pending_sessions WHERE token_hash=?", (_token_hash(token),))
