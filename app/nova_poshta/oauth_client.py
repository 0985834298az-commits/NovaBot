"""Nova Poshta Business Cabinet OAuth (Authorization Code + PKCE)."""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import aiohttp
from loguru import logger

from app.nova_poshta.oauth_constants import (
    OAUTH_AUDIENCE,
    OAUTH_AUTHORIZATION_ENDPOINT,
    OAUTH_CLIENT_ID,
    OAUTH_CLIENT_SECRET,
    OAUTH_DEFAULT_LANGUAGE,
    OAUTH_REDIRECT_URI,
    OAUTH_REFRESH_SKEW_SECONDS,
    OAUTH_SCOPE,
    OAUTH_TOKEN_ENDPOINT,
)
from app.utils.ssl import create_ssl_context


@dataclass(frozen=True, slots=True)
class PkceChallenge:
    """PKCE verifier/challenge pair."""

    code_verifier: str
    code_challenge: str
    state: str
    nonce: str


@dataclass(frozen=True, slots=True)
class OAuthTokenSet:
    """Tokens returned by the OAuth token endpoint."""

    access_token: str
    refresh_token: str
    id_token: str
    expires_at: datetime
    scope: str
    token_type: str


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def generate_pkce() -> PkceChallenge:
    """Create a new PKCE S256 challenge (observed cabinet flow)."""
    code_verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(code_verifier.encode("ascii")).digest())
    state = _b64url(secrets.token_bytes(32))
    nonce = state
    return PkceChallenge(
        code_verifier=code_verifier,
        code_challenge=challenge,
        state=state,
        nonce=nonce,
    )


def build_authorization_url(
    pkce: PkceChallenge,
    *,
    login_hint: str | None = None,
) -> str:
    """Build the /oauth2/auth URL used by the Business Cabinet."""
    params: dict[str, str] = {
        "response_type": "code",
        "client_id": OAUTH_CLIENT_ID,
        "state": pkce.state,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "scope": OAUTH_SCOPE,
        "code_challenge": pkce.code_challenge,
        "code_challenge_method": "S256",
        "nonce": pkce.nonce,
        "audience": OAUTH_AUDIENCE,
        "default_language": OAUTH_DEFAULT_LANGUAGE,
    }
    if login_hint:
        params["login_hint"] = login_hint
    return f"{OAUTH_AUTHORIZATION_ENDPOINT}?{urlencode(params)}"


def _expires_at_from_payload(payload: dict[str, Any]) -> datetime:
    expires_in = int(payload.get("expires_in") or 0)
    if expires_in <= 0:
        expires_in = 3600
    return datetime.now(timezone.utc) + timedelta(seconds=expires_in)


def parse_token_response(payload: dict[str, Any]) -> OAuthTokenSet:
    """Parse and validate a token endpoint JSON body."""
    access_token = str(payload.get("access_token") or "").strip()
    refresh_token = str(payload.get("refresh_token") or "").strip()
    if not access_token or not refresh_token:
        msg = "OAuth token response missing access_token or refresh_token"
        raise ValueError(msg)
    return OAuthTokenSet(
        access_token=access_token,
        refresh_token=refresh_token,
        id_token=str(payload.get("id_token") or "").strip(),
        expires_at=_expires_at_from_payload(payload),
        scope=str(payload.get("scope") or OAUTH_SCOPE),
        token_type=str(payload.get("token_type") or "bearer"),
    )


async def _post_token(form: dict[str, str]) -> OAuthTokenSet:
    connector = aiohttp.TCPConnector(ssl=create_ssl_context())
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.post(
            OAUTH_TOKEN_ENDPOINT,
            data=form,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://new.novaposhta.ua/",
            },
        ) as response:
            text = await response.text()
            try:
                payload = await response.json(content_type=None)
            except Exception as exc:
                msg = f"OAuth token endpoint returned non-JSON (HTTP {response.status}): {text[:300]}"
                raise ValueError(msg) from exc
            if response.status >= 400 or not isinstance(payload, dict):
                msg = f"OAuth token endpoint failed (HTTP {response.status}): {text[:500]}"
                raise ValueError(msg)
            logger.info(
                "OAuth token exchange OK: keys={} expires_in={}",
                sorted(payload.keys()),
                payload.get("expires_in"),
            )
            return parse_token_response(payload)


async def exchange_authorization_code(
    *,
    code: str,
    code_verifier: str,
) -> OAuthTokenSet:
    """Exchange authorization code + PKCE verifier for tokens."""
    return await _post_token(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "code_verifier": code_verifier,
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
        },
    )


async def refresh_access_token(refresh_token: str) -> OAuthTokenSet:
    """Refresh access_token using stored refresh_token."""
    return await _post_token(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
        },
    )


def needs_refresh(expires_at: datetime, *, skew_seconds: int = OAUTH_REFRESH_SKEW_SECONDS) -> bool:
    """Return True when access_token should be refreshed."""
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at - timedelta(seconds=skew_seconds) <= datetime.now(timezone.utc)
