import time
import asyncio
import pytest
import httpx
from authlib.jose import JsonWebKey, JsonWebToken
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from fastapi.testclient import TestClient
from app import auth
from app.main import app
from app.services.accounts import database
from test_planner_api import valid_request

HEADERS = {"Origin": "http://localhost:3000"}


def login(client):
    result = client.post("/api/v1/auth/mock", headers=HEADERS)
    assert result.status_code == 200
    return result.json()["user"]


def test_session_role_logout_return_and_expiry():
    with TestClient(app) as client:
        assert client.get("/api/v1/auth/session").json()["user"] is None
        user = login(client)
        first_token = client.cookies.get(auth.SESSION_COOKIE)
        response = client.post("/api/v1/auth/role", json={"role": "visitor"}, headers=HEADERS)
        assert response.json()["user"]["role"] == "visitor"
        assert "HttpOnly" in client.post("/api/v1/auth/mock", headers=HEADERS).headers["set-cookie"]
        assert client.cookies.get(auth.SESSION_COOKIE) != first_token
        assert client.post("/api/v1/auth/logout", headers=HEADERS).status_code == 200
        assert client.get("/api/v1/auth/session").json()["user"] is None
        returning = login(client)
        assert returning["id"] == user["id"] and returning["role"] == "visitor"
        with database() as db:
            db.execute("UPDATE sessions SET expires=?", (time.time() - 1,))
        assert client.get("/api/v1/auth/session").json()["user"] is None


def test_cookie_mutations_require_origin_and_login():
    with TestClient(app) as client:
        assert client.post("/api/v1/auth/mock").status_code == 403
        assert client.post("/api/v1/auth/mock", headers={"Origin": "https://example.com"}).status_code == 403
        assert client.post("/api/v1/auth/role", json={"role": "planner"}, headers=HEADERS).status_code == 401
        assert client.post("/api/v1/planner/analyses", json=valid_request(), headers=HEADERS).status_code == 401
        login(client)
        assert client.post("/api/v1/auth/role", json={"role": "admin"}, headers=HEADERS).status_code == 422
        assert client.post("/api/v1/auth/logout").status_code == 403


@pytest.mark.parametrize("changed", [None, "aud", "iss", "nonce", "exp", "azp", "sub", "signature"])
def test_google_signed_id_token_validation(monkeypatch, changed):
    monkeypatch.setenv("HEUNGMAP_AUTH_MODE", "google")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    private = JsonWebKey.generate_key("RSA", 2048, is_private=True, options={"kid": "test"})
    claims = {"sub": "google-user", "iss": "https://accounts.google.com", "aud": "client",
              "iat": int(time.time()), "exp": int(time.time()) + 300, "nonce": "nonce"}
    if changed == "exp":
        claims["exp"] = int(time.time()) - 300
    elif changed == "sub":
        claims.pop("sub")
    elif changed and changed != "signature":
        claims[changed] = "wrong"
    signing_key = JsonWebKey.generate_key("RSA", 2048, is_private=True, options={"kid": "test"}) if changed == "signature" else private
    token = JsonWebToken(["RS256"]).encode({"alg": "RS256", "kid": "test"}, claims, signing_key).decode()
    async_client = httpx.AsyncClient
    def respond(request):
        if request.url.path == "/token":
            assert b"code_verifier=verifier" in request.content
            return httpx.Response(200, json={"id_token": token})
        return httpx.Response(200, json={"keys": [private.as_dict(is_private=False)]})
    monkeypatch.setattr(auth.httpx, "AsyncClient", lambda **kwargs: async_client(transport=httpx.MockTransport(respond), **kwargs))
    if changed:
        with pytest.raises(Exception):
            asyncio.run(auth.google_identity("code", {"nonce": "nonce", "verifier": "verifier"}))
        with database() as db:
            assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    else:
        assert asyncio.run(auth.google_identity("code", {"nonce": "nonce", "verifier": "verifier"}))["provider"] == "google"


def test_production_rejects_mock_and_http(monkeypatch):
    monkeypatch.setenv("HEUNGMAP_ENV", "production")
    import pytest
    with pytest.raises(RuntimeError):
        auth.mode()
    monkeypatch.setenv("HEUNGMAP_AUTH_MODE", "google")
    with pytest.raises(RuntimeError):
        auth.mode()
    monkeypatch.setenv("HEUNGMAP_PUBLIC_ORIGIN", "https://example.com")
    assert auth.mode() == "google"


def test_google_state_pkce_single_use_and_returning_role(monkeypatch):
    monkeypatch.setenv("HEUNGMAP_AUTH_MODE", "google")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    async def verified_identity(code, flow):
        assert code == "test-code" and flow["nonce"] and len(flow["verifier"]) >= 43
        return auth.identity("google", "test-subject", "테스트")
    monkeypatch.setattr(auth, "google_identity", verified_identity)
    with TestClient(app, follow_redirects=False) as client:
        assert client.post("/api/v1/auth/mock", headers=HEADERS).status_code == 404
        start = client.get("/api/v1/auth/google")
        params = parse_qs(urlsplit(start.headers["location"]).query)
        assert params["code_challenge_method"] == ["S256"]
        assert params["redirect_uri"] == ["http://localhost:3000/api/v1/auth/google/callback"]
        bad = client.get("/api/v1/auth/google/callback?state=wrong&code=test-code")
        assert "auth_error" in bad.headers["location"]
        assert client.get("/api/v1/auth/session").json()["user"] is None
        start = client.get("/api/v1/auth/google")
        state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
        flow_cookie = client.cookies.get(auth.FLOW_COOKIE)
        callback = "/api/v1/auth/google/callback?state=" + state + "&code=test-code"
        assert client.get(callback).headers["location"].endswith("/onboarding")
        client.post("/api/v1/auth/role", json={"role": "planner"}, headers=HEADERS)
        client.post("/api/v1/auth/logout", headers=HEADERS)
        client.cookies.set(auth.FLOW_COOKIE, flow_cookie)
        assert "auth_error" in client.get(callback).headers["location"]
        client.cookies.delete(auth.FLOW_COOKIE)
        start = client.get("/api/v1/auth/google")
        state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
        assert client.get("/api/v1/auth/google/callback?state=" + state + "&code=test-code").headers["location"].endswith("/planner")


def test_publish_shared_prediction_ownership_private_fields_and_withdraw():
    with TestClient(app) as owner, TestClient(app) as other:
        login(owner)
        owner.post("/api/v1/auth/role", json={"role": "planner"}, headers=HEADERS)
        payload = valid_request()
        payload["client_request_id"] = str(uuid4())
        payload["event_draft"]["venue"] = {"name": "확정 장소", "address": "서울"}
        analysis = owner.post("/api/v1/planner/analyses", json=payload, headers=HEADERS).json()
        body = {"analysis_id": analysis["analysis_id"], "description": "공개할 소개문", "consent": True}
        login(other)
        other.post("/api/v1/auth/role", json={"role": "planner"}, headers=HEADERS)
        assert other.post("/api/v1/planner/publications", json=body, headers=HEADERS).status_code == 409
        assert owner.post("/api/v1/planner/publications", json={**body, "consent": False}, headers=HEADERS).status_code == 422
        result = owner.post("/api/v1/planner/publications", json=body, headers=HEADERS)
        assert result.status_code == 200, result.text
        event_id = result.json()["event_id"]
        assert owner.get("/api/v1/events/" + event_id).json()["description"] == body["description"]
        prediction = owner.get("/api/v1/events/" + event_id + "/prediction").json()
        assert prediction["prediction_id"] == analysis["prediction"]["prediction_id"]
        assert prediction["primary_metric"] == analysis["prediction"]["primary_metric"]
        assert prediction["evidence"] == [] and prediction["factors"] == []
        assert "budget" not in result.text and "10000000" not in str(prediction)
        assert other.delete("/api/v1/planner/publications/" + event_id, headers=HEADERS).status_code == 404
        assert owner.delete("/api/v1/planner/publications/" + event_id, headers=HEADERS).status_code == 200
        assert owner.get("/api/v1/events/" + event_id).status_code == 404
