"""Interactive Business Cabinet OAuth login (Authorization Code + PKCE)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

from loguru import logger

from app.nova_poshta.oauth_client import (
    OAuthTokenSet,
    build_authorization_url,
    exchange_authorization_code,
    generate_pkce,
)
from app.nova_poshta.oauth_constants import OAUTH_REDIRECT_URI


@dataclass(frozen=True, slots=True)
class BrowserLoginResult:
    """Result of a browser-assisted OAuth login."""

    tokens: OAuthTokenSet
    redirect_url: str


def _extract_code_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    if "auth-processing" not in parsed.path:
        return None
    values = parse_qs(parsed.query).get("code") or []
    if not values:
        return None
    code = str(values[0]).strip()
    return code or None


async def login_with_browser(
    *,
    login_hint: str | None = None,
    timeout_seconds: float = 600,
    headless: bool = False,
) -> BrowserLoginResult:
    """
    Open the Business Cabinet OAuth authorize URL and wait for redirect with code.

    Requires Playwright + Chromium. User completes login/consent in the browser.
    Password grant is not available on this IdP; interactive login is required once.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        msg = (
            "Playwright is required for OAuth browser login. "
            "Install with: pip install playwright && playwright install chromium"
        )
        raise RuntimeError(msg) from exc

    pkce = generate_pkce()
    auth_url = build_authorization_url(pkce, login_hint=login_hint)
    logger.info("Opening NP OAuth authorize URL (PKCE S256)")

    async with async_playwright() as playwright:
        browser = None
        launch_errors: list[str] = []
        # Prefer installed Chrome/Edge so login works without playwright browser download.
        for kwargs in (
            {"channel": "chrome", "headless": headless},
            {"channel": "msedge", "headless": headless},
            {"headless": headless},
        ):
            try:
                browser = await playwright.chromium.launch(**kwargs)
                break
            except Exception as exc:  # noqa: BLE001 — try next browser channel
                launch_errors.append(f"{kwargs}: {exc}")
        if browser is None:
            msg = (
                "Failed to launch a browser for OAuth login. "
                "Install Chrome or run: playwright install chromium. "
                f"Errors: {' | '.join(launch_errors)}"
            )
            raise RuntimeError(msg)

        context = await browser.new_context()
        page = await context.new_page()

        code_holder: dict[str, Any] = {"code": None, "url": None}

        def _maybe_capture(url: str) -> None:
            code = _extract_code_from_url(url)
            if code and not code_holder["code"]:
                code_holder["code"] = code
                code_holder["url"] = url

        page.on("framenavigated", lambda frame: _maybe_capture(frame.url))
        await page.goto(auth_url, wait_until="domcontentloaded")

        try:
            await page.wait_for_url(
                lambda url: _extract_code_from_url(url) is not None,
                timeout=int(timeout_seconds * 1000),
            )
            _maybe_capture(page.url)
        except Exception as exc:
            await browser.close()
            if not code_holder["code"]:
                msg = (
                    f"OAuth login timed out after {timeout_seconds:.0f}s "
                    f"(expected redirect to {OAUTH_REDIRECT_URI}?code=...)"
                )
                raise TimeoutError(msg) from exc

        if not code_holder["code"]:
            _maybe_capture(page.url)
        if not code_holder["code"]:
            await browser.close()
            msg = "OAuth redirect observed but authorization code was missing"
            raise RuntimeError(msg)

        code = str(code_holder["code"])
        redirect_url = str(code_holder["url"] or page.url)
        await browser.close()

    tokens = await exchange_authorization_code(
        code=code,
        code_verifier=pkce.code_verifier,
    )
    logger.info(
        "OAuth authorization code exchanged; expires_at={}",
        tokens.expires_at.isoformat(),
    )
    return BrowserLoginResult(tokens=tokens, redirect_url=redirect_url)
