"""Exercise real OIDC crypto and SQLite; replace only the remote HTTP server."""

import base64
import hashlib
import json
import time
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from procurement_ontology.identity import IdentityStore


@pytest.fixture
def oidc(tmp_path):
    from procurement_ontology.sso import SSOClient, SSOConfig
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="test-key", alg="RS256", use="sig")
    data = {"claims": {}, "userinfo": {}, "metadata": {}, "bad_signature": False, "network_error": False}
    issuer = "https://sso.example"
    def remote(request):
        if data["network_error"]:
            raise httpx.ConnectError("unavailable", request=request)
        if request.url.path == "/.well-known/openid-configuration":
            return httpx.Response(200, json={"issuer": issuer, "authorization_endpoint": issuer + "/authorize",
                "token_endpoint": issuer + "/token", "userinfo_endpoint": issuer + "/userinfo",
                "jwks_uri": issuer + "/jwks", "id_token_signing_alg_values_supported": ["RS256"], **data["metadata"]})
        if request.url.path == "/token":
            form = parse_qs(request.content.decode())
            assert request.headers["Authorization"] == "Basic " + base64.b64encode(b"client:synthetic-secret").decode()
            assert form["grant_type"] == ["authorization_code"]
            assert form["code"] == ["valid-code"]
            assert form["redirect_uri"] == ["https://ontology.example/v1/auth/sso/callback"]
            challenge = base64.urlsafe_b64encode(hashlib.sha256(form["code_verifier"][0].encode()).digest()).rstrip(b"=").decode()
            assert challenge == data["authorize"]["code_challenge"][0]
            now = int(time.time())
            claims = {"iss": issuer, "aud": "client", "sub": "member:1:7", "iat": now, "exp": now + 300,
                      "auth_time": now - 60, "nonce": data["authorize"]["nonce"][0], **data["claims"]}
            signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048) if data["bad_signature"] else key
            return httpx.Response(200, json={"access_token": "synthetic-opaque-access", "token_type": "Bearer",
                "id_token": jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": "test-key"})})
        if request.url.path == "/jwks":
            return httpx.Response(200, json={"keys": [jwk]})
        if request.url.path == "/userinfo":
            assert request.headers["Authorization"] == "Bearer synthetic-opaque-access"
            return httpx.Response(200, json={"sub": "member:1:7", "preferred_username": "SSO user", "tenant_id": 1,
                                           **data["userinfo"]})
        raise AssertionError(str(request.url))
    store = IdentityStore(tmp_path / "control.sqlite3")
    config = SSOConfig(issuer, "client", "synthetic-secret", "https://ontology.example/v1/auth/sso/callback")
    client = SSOClient(config, store, http_client=httpx.Client(transport=httpx.MockTransport(remote)))
    yield client, store, data
    client.close()


def begin(oidc):
    client, store, data = oidc
    url, binding = client.start()
    data["authorize"] = parse_qs(urlparse(url).query)
    assert data["authorize"]["response_type"] == ["code"]
    assert data["authorize"]["scope"] == ["openid profile"]
    assert data["authorize"]["code_challenge_method"] == ["S256"]
    assert "synthetic-secret" not in url
    return data["authorize"]["state"][0], binding


def test_code_flow_validates_identity_and_consumes_transaction(oidc):
    from procurement_ontology.sso import SSOError
    client, store, _ = oidc
    state, binding = begin(oidc)
    assert state.encode() not in store.path.read_bytes()
    assert binding.encode() not in store.path.read_bytes()
    assert client.finish(state, binding, "valid-code") == {
        "issuer": "https://sso.example", "sub": "member:1:7", "username": "SSO user"}
    with pytest.raises(SSOError):
        client.finish(state, binding, "valid-code")


@pytest.mark.parametrize("claims", [
    {"iss": "https://evil.example"}, {"aud": "other-client"}, {"nonce": "wrong"},
    {"exp": 1}, {"iat": 9999999999}, {"sub": ""}, {"auth_time": "not-a-number"},
    {"auth_time": True}, {"auth_time": 9999999999}, {"azp": "other-client"},
    {"aud": ["client", "other-client"]},
])
def test_invalid_id_token_never_authenticates(oidc, claims):
    from procurement_ontology.sso import SSOError
    client, _, data = oidc
    state, binding = begin(oidc)
    data["claims"] = claims
    with pytest.raises(SSOError):
        client.finish(state, binding, "valid-code")


@pytest.mark.parametrize("fault", ["signature", "userinfo", "network"])
def test_invalid_signature_userinfo_or_network_fails_closed(oidc, fault):
    from procurement_ontology.sso import SSOError
    client, _, data = oidc
    state, binding = begin(oidc)
    if fault == "signature":
        data["bad_signature"] = True
    elif fault == "userinfo":
        data["userinfo"] = {"sub": "someone-else"}
    else:
        data["network_error"] = True
    with pytest.raises(SSOError):
        client.finish(state, binding, "valid-code")


def test_wrong_browser_does_not_consume_legitimate_transaction(oidc):
    from procurement_ontology.sso import SSOError
    client, _, _ = oidc
    state, binding = begin(oidc)
    for bad_state, bad_binding in (("wrong", binding), (state, "other-browser")):
        with pytest.raises(SSOError):
            client.finish(bad_state, bad_binding, "valid-code")
    assert client.finish(state, binding, "valid-code")["sub"] == "member:1:7"


def test_expired_transaction_fails(oidc):
    from procurement_ontology.sso import SSOError
    client, store, _ = oidc
    state, binding = begin(oidc)
    with store._db() as db:
        db.execute("UPDATE sso_transactions SET expires_at=0")
    with pytest.raises(SSOError):
        client.finish(state, binding, "valid-code")


@pytest.mark.parametrize("metadata", [
    {"issuer": "https://other.example"}, {"token_endpoint": "https://other.example/token"},
    {"jwks_uri": "http://sso.example/jwks"}, {"userinfo_endpoint": "https://user:pass@sso.example/info"},
])
def test_untrusted_metadata_is_rejected(oidc, metadata):
    from procurement_ontology.sso import SSOError
    client, _, data = oidc
    data["metadata"] = metadata
    with pytest.raises(SSOError):
        client.start()


def test_missing_or_partial_configuration_leaves_password_mode_available(monkeypatch):
    from procurement_ontology.sso import SSOConfig
    for name in ("ISSUER", "CLIENT_ID", "CLIENT_SECRET", "REDIRECT_URI"):
        monkeypatch.delenv("PROCUREMENT_SSO_" + name, raising=False)
    assert SSOConfig.from_env() is None
    monkeypatch.setenv("PROCUREMENT_SSO_CLIENT_ID", "client")
    assert SSOConfig.from_env() is None
