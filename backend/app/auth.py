from __future__ import annotations

import base64
import hashlib
import os
import secrets
import time
from typing import Literal
from urllib.parse import urlencode, urlsplit

import httpx
from authlib.jose import JsonWebToken
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from app.services.accounts import database, digest, identity, issue_session, revoke, session_user

AUTH_ERRORS = {status: {"description": message, "content": {"application/problem+json": {
    "schema": {"$ref": "#/components/schemas/Problem"}}}} for status, message in {
        401: "로그인 필요", 403: "권한 또는 origin 오류", 404: "사용할 수 없는 대상",
        409: "분석 상태 충돌", 422: "입력 검증 오류", 503: "인증 서비스 설정 또는 연결 오류"}.items()}
router = APIRouter(prefix="/api/v1/auth", tags=["auth"], responses=AUTH_ERRORS)
SESSION_COOKIE = "heungmap_session"
FLOW_COOKIE = "heungmap_oauth"
MOCK_COOKIE = "heungmap_demo"


def origin() -> str:
    value = os.getenv("HEUNGMAP_PUBLIC_ORIGIN", "http://localhost:3000").rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username:
        raise RuntimeError("HEUNGMAP_PUBLIC_ORIGIN must be an origin without a path")
    if os.getenv("HEUNGMAP_ENV", "development") == "production" and parsed.scheme != "https":
        raise RuntimeError("Production requires HTTPS")
    return value


def mode() -> str:
    value = os.getenv("HEUNGMAP_AUTH_MODE", "mock")
    if value not in {"mock", "google"}:
        raise RuntimeError("Unsupported auth mode")
    if value == "mock" and os.getenv("HEUNGMAP_ENV", "development") != "development":
        raise RuntimeError("Mock authentication is only allowed in development")
    origin()
    return value


def cookie(response, name: str, value: str, age: int):
    response.set_cookie(name, value, max_age=age, httponly=True,
                        secure=origin().startswith("https:"), samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"


def same_origin(request: Request):
    # Require Origin on cookie-authenticated writes, including login/logout.
    if request.headers.get("origin") != origin():
        raise HTTPException(403, "요청 출처를 확인할 수 없습니다.")


def require_user(request: Request) -> dict:
    user = session_user(request.cookies.get(SESSION_COOKIE))
    if not user:
        raise HTTPException(401, "로그인이 필요합니다.")
    return user


class RoleRequest(BaseModel):
    role: Literal["planner", "visitor"]


class SessionUser(BaseModel):
    id: str
    name: str
    role: Literal["planner", "visitor"] | None
    provider: Literal["mock", "google"]


class SessionResponse(BaseModel):
    user: SessionUser | None
    mode: Literal["mock", "google"]


@router.get("/session", response_model=SessionResponse, operation_id="getSession")
def get_session(request: Request):
    return JSONResponse({"user": session_user(request.cookies.get(SESSION_COOKIE)), "mode": mode()},
                        headers={"Cache-Control": "no-store"})


@router.post("/mock", response_model=SessionResponse, operation_id="mockLogin")
def mock_login(request: Request):
    same_origin(request)
    if mode() != "mock":
        raise HTTPException(404, "사용할 수 없는 로그인 방식입니다.")
    # Persistent, HttpOnly demo identity restores role after logout, per browser.
    subject = request.cookies.get(MOCK_COOKIE) or secrets.token_urlsafe(32)
    user = identity("mock", digest(subject), "체험 사용자")
    revoke(request.cookies.get(SESSION_COOKIE))
    response = JSONResponse({"user": user, "mode": "mock"})
    cookie(response, MOCK_COOKIE, subject, 86400 * 365)
    cookie(response, SESSION_COOKIE, issue_session(user["id"]), 86400 * 7)
    return response


@router.post("/role", response_model=SessionResponse, operation_id="setRole")
def set_role(body: RoleRequest, request: Request):
    same_origin(request)
    user = require_user(request)
    with database() as db:
        db.execute("UPDATE users SET role=? WHERE id=?", (body.role, user["id"]))
    user["role"] = body.role
    return JSONResponse({"user": user, "mode": mode()}, headers={"Cache-Control": "no-store"})


@router.post("/logout", operation_id="logout")
def logout(request: Request):
    same_origin(request)
    revoke(request.cookies.get(SESSION_COOKIE))
    response = JSONResponse({"ok": True}, headers={"Cache-Control": "no-store"})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


def google_settings():
    if mode() != "google":
        raise HTTPException(404, "Google 로그인은 아직 연결하지 않았습니다.")
    client_id, secret = os.getenv("GOOGLE_CLIENT_ID"), os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not secret:
        raise HTTPException(503, "Google 로그인 설정이 필요합니다.")
    return client_id, secret


@router.get("/google", operation_id="startGoogleLogin")
def google_login():
    client_id, _ = google_settings()
    token, state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(4))
    with database() as db:
        db.execute("DELETE FROM oauth_transactions WHERE expires<?", (time.time(),))
        db.execute("INSERT INTO oauth_transactions VALUES (?, ?, ?, ?, ?)",
                   (digest(token), state, nonce, verifier, time.time() + 600))
    params = {
        "client_id": client_id, "redirect_uri": origin() + "/api/v1/auth/google/callback",
        "response_type": "code", "scope": "openid profile email", "state": state, "nonce": nonce,
        "code_challenge": base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode(),
        "code_challenge_method": "S256",
    }
    response = RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))
    cookie(response, FLOW_COOKIE, token, 600)
    return response


async def google_identity(code: str, flow: dict) -> dict:
    client_id, secret = google_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        result = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": client_id, "client_secret": secret,
            "redirect_uri": origin() + "/api/v1/auth/google/callback",
            "grant_type": "authorization_code", "code_verifier": flow["verifier"],
        })
        result.raise_for_status()
        keys = await client.get("https://www.googleapis.com/oauth2/v3/certs")
        keys.raise_for_status()
    claims = JsonWebToken(["RS256"]).decode(result.json()["id_token"], keys.json(), claims_options={
        "iss": {"essential": True, "values": ["https://accounts.google.com", "accounts.google.com"]},
        "aud": {"essential": True, "value": client_id},
        "exp": {"essential": True}, "iat": {"essential": True},
        "sub": {"essential": True}, "nonce": {"essential": True, "value": flow["nonce"]},
    })
    claims.validate(leeway=60)
    if not isinstance(claims["sub"], str) or not claims["sub"]:
        raise ValueError("Missing subject")
    if claims.get("azp", client_id) != client_id:
        raise ValueError("Invalid authorized party")
    # Tokens are used once for identity verification and are never persisted.
    return identity("google", claims["sub"], str(claims.get("name") or "사용자"))


@router.get("/google/callback", operation_id="finishGoogleLogin")
async def google_callback(request: Request):
    google_settings()
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM oauth_transactions WHERE token_hash=?",
                         (digest(request.cookies.get(FLOW_COOKIE, "")),)).fetchone()
        db.execute("DELETE FROM oauth_transactions WHERE token_hash=?",
                   (digest(request.cookies.get(FLOW_COOKIE, "")),))
    flow = dict(row) if row else None
    response = RedirectResponse(origin() + "/?auth_error=1", status_code=303)
    response.delete_cookie(FLOW_COOKIE, path="/")
    response.headers["Cache-Control"] = "no-store"
    if not flow or flow["expires"] < time.time() or not secrets.compare_digest(flow["state"], request.query_params.get("state", "")):
        return response
    if request.query_params.get("error") or not request.query_params.get("code"):
        return response
    try:
        user = await google_identity(request.query_params["code"], flow)
    except (httpx.HTTPError, ValueError, KeyError):
        return response
    except Exception:
        # OIDC/JWT validation failures must never create a session or expose tokens.
        return response
    revoke(request.cookies.get(SESSION_COOKIE))
    response.headers["location"] = origin() + ("/" + user["role"] if user["role"] else "/onboarding")
    cookie(response, SESSION_COOKIE, issue_session(user["id"]), 86400 * 7)
    return response
