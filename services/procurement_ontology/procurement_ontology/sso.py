"""Confidential OIDC code flow; only verified subjects reach the identity store."""

import base64
import hashlib
import os
import secrets
import ssl
import time
from dataclasses import dataclass, field
from urllib.parse import quote_plus, urlencode, urlsplit

import httpx
import jwt

from .identity import _token_hash


class SSOError(Exception):
    pass


@dataclass(frozen=True)
class SSOConfig:
    issuer: str
    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str

    @classmethod
    def from_env(cls):
        values = [os.getenv("PROCUREMENT_SSO_" + key, "") for key in
                  ("ISSUER", "CLIENT_ID", "CLIENT_SECRET", "REDIRECT_URI")]
        return cls(*values) if all(values) else None


class SSOClient:
    def __init__(self, config, identities, *, http_client=None):
        self.config, self.identities = config, identities
        self.http = http_client or httpx.Client(timeout=10, follow_redirects=False, trust_env=False,
                                               verify=ssl.create_default_context())
        with identities._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS sso_transactions (
                state_hash TEXT PRIMARY KEY, binding_hash TEXT NOT NULL,
                nonce TEXT NOT NULL, verifier TEXT NOT NULL, expires_at REAL NOT NULL
            )""")

    def close(self):
        self.http.close()

    @staticmethod
    def _https(url):
        if not isinstance(url, str):
            raise ValueError("协议地址必须是字符串")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError("需要固定 HTTPS 地址")
        return parsed

    def _json(self, url, **kwargs):
        response = self.http.request("POST" if "data" in kwargs else "GET", url, **kwargs)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("响应不是对象")
        return result

    def _metadata(self):
        origin = self._https(self.config.issuer)
        callback = self._https(self.config.redirect_uri)
        if origin.query or callback.query or callback.path != "/v1/auth/sso/callback":
            raise ValueError("无效协议地址")
        metadata = self._json(self.config.issuer.rstrip("/") + "/.well-known/openid-configuration")
        if metadata.get("issuer") != self.config.issuer:
            raise ValueError("issuer 不匹配")
        for name in ("authorization_endpoint", "token_endpoint", "userinfo_endpoint", "jwks_uri"):
            endpoint = self._https(metadata[name])
            if endpoint.netloc != origin.netloc:
                raise ValueError("协议端点必须属于固定 issuer")
        if "RS256" not in metadata.get("id_token_signing_alg_values_supported", []):
            raise ValueError("不支持的签名算法")
        return metadata

    def start(self):
        try:
            metadata = self._metadata()
            state, nonce, verifier, binding = (secrets.token_urlsafe(32) for _ in range(4))
            with self.identities._db() as db:
                db.execute("DELETE FROM sso_transactions WHERE expires_at<=?", (time.time(),))
                db.execute("INSERT INTO sso_transactions VALUES (?,?,?,?,?)",
                           (_token_hash(state), _token_hash(binding), nonce, verifier, time.time() + 300))
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            query = urlencode({"response_type": "code", "client_id": self.config.client_id,
                "redirect_uri": self.config.redirect_uri, "scope": "openid profile", "state": state,
                "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256"})
            separator = "&" if urlsplit(metadata["authorization_endpoint"]).query else "?"
            return metadata["authorization_endpoint"] + separator + query, binding
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            raise SSOError("SSO 登录暂不可用，请稍后重试") from None

    def finish(self, state, binding, code):
        try:
            if not state or not binding or not code or max(len(state), len(binding), len(code)) > 4096:
                raise ValueError("缺少登录凭据")
            with self.identities._db() as db:
                db.execute("BEGIN IMMEDIATE")
                transaction = db.execute("SELECT * FROM sso_transactions WHERE state_hash=? AND binding_hash=? AND expires_at>?",
                                         (_token_hash(state), _token_hash(binding), time.time())).fetchone()
                if not transaction:
                    raise ValueError("登录事务无效")
                db.execute("DELETE FROM sso_transactions WHERE state_hash=?", (_token_hash(state),))
            metadata = self._metadata()
            tokens = self._json(metadata["token_endpoint"],
                                auth=(quote_plus(self.config.client_id, safe=""), quote_plus(self.config.client_secret, safe="")),
                                data={"grant_type": "authorization_code", "code": code,
                                      "redirect_uri": self.config.redirect_uri, "code_verifier": transaction["verifier"]})
            if str(tokens.get("token_type", "")).lower() != "bearer":
                raise ValueError("无效令牌类型")
            header = jwt.get_unverified_header(tokens["id_token"])
            if header.get("alg") != "RS256" or not header.get("kid"):
                raise ValueError("无效签名头")
            keys = self._json(metadata["jwks_uri"])["keys"]
            matches = [key for key in keys if key.get("kid") == header["kid"] and key.get("kty") == "RSA"
                       and key.get("use", "sig") == "sig" and key.get("alg", "RS256") == "RS256"
                       and "verify" in key.get("key_ops", ["verify"])]
            if len(matches) != 1:
                raise ValueError("签名公钥无效")
            key = jwt.PyJWK.from_dict(matches[0], algorithm="RS256").key
            claims = jwt.decode(tokens["id_token"], key, algorithms=["RS256"], audience=self.config.client_id,
                                issuer=self.config.issuer, leeway=60,
                                options={"require": ["iss", "aud", "exp", "iat", "sub", "nonce", "auth_time"]})
            subject = claims["sub"]
            if not isinstance(subject, str) or not 1 <= len(subject) <= 255 or any(ord(c) < 33 or ord(c) > 126 for c in subject):
                raise ValueError("无效 subject")
            if not isinstance(claims["nonce"], str) or not secrets.compare_digest(claims["nonce"], transaction["nonce"]):
                raise ValueError("nonce 不匹配")
            if claims.get("azp", self.config.client_id) != self.config.client_id or (
                isinstance(claims["aud"], list) and len(claims["aud"]) > 1 and "azp" not in claims
            ):
                raise ValueError("azp 不匹配")
            auth_time = claims["auth_time"]
            if type(auth_time) is not int or auth_time < 0 or auth_time > min(time.time(), claims["iat"]) + 60:
                raise ValueError("auth_time 无效")
            user = self._json(metadata["userinfo_endpoint"], headers={"Authorization": "Bearer " + tokens["access_token"]})
            if user.get("sub") != subject or not isinstance(user.get("preferred_username", ""), str):
                raise ValueError("UserInfo 身份不匹配")
            return {"issuer": self.config.issuer, "sub": subject, "username": user.get("preferred_username", "")}
        except (httpx.HTTPError, jwt.PyJWTError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
            raise SSOError("SSO 登录失败，请重新开始登录") from None
