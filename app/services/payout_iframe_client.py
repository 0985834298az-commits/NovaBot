"""NovaPay payout iframe client — observed CDP capture flow (2026-07-27).

Flow:
1. Payment.initPayout (Nova Poshta API)
2. GET {Url}&lang=ua (NovaPay iframe session + CSRF from page)
3. GET /locales/uk.json (browser does this before check-otp)
4. POST /api/check-otp
5. POST /api/payout?sid={Id} with {"pan": "..."}
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import aiohttp
from loguru import logger

from app.nova_poshta.client import NovaPoshtaClient
from app.nova_poshta.exceptions import NovaPoshtaApiError
from app.services.ttn_service import normalize_phone
from app.utils.payment_card import mask_card_number
from app.utils.ssl import create_ssl_context

NOVAPAY_ORIGIN = "https://e-com.novapay.ua"
CHECK_OTP_URL = f"{NOVAPAY_ORIGIN}/api/check-otp"
PAYOUT_API_URL = f"{NOVAPAY_ORIGIN}/api/payout"
LOCALES_UK_URL = f"{NOVAPAY_ORIGIN}/locales/uk.json"

# Observed browser UA on successful check-otp / payout (CDP 2026-07-27).
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)
_BROWSER_HEADERS = {
    "User-Agent": _BROWSER_UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "uk-UA,uk;q=0.9",
}
_CSRF_COOKIE_NAMES = ("_csrf", "csrfToken", "XSRF-TOKEN", "xsrf-token")


@dataclass(frozen=True, slots=True)
class PayoutCardRegistration:
    """Result of the observed NovaPay add-card flow."""

    payout_id: str
    masked_pan: str
    int_doc_number: str
    init_id: str
    init_url: str


def build_payout_iframe_url(base_url: str) -> str:
    """Open iframe like the business cabinet: ``{Url}&lang=ua``."""
    if "lang=" in base_url:
        return base_url
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}lang=ua"


def _init_payout_phone(phone: str) -> str:
    normalized = normalize_phone(phone) or phone.strip()
    if not normalized:
        msg = "Cash2Card requires a valid sender phone number"
        raise NovaPoshtaApiError(msg)
    return normalized


def _check_otp_phone(phone: str) -> str:
    normalized = _init_payout_phone(phone)
    return normalized if normalized.startswith("+") else f"+{normalized}"


def _csrf_from_response(response: aiohttp.ClientResponse) -> str | None:
    for name in _CSRF_COOKIE_NAMES:
        cookie = response.cookies.get(name)
        if cookie is not None and cookie.value:
            return cookie.value
    return None


def _csrf_from_jar(jar: aiohttp.CookieJar, page_url: str) -> str | None:
    cookies = jar.filter_cookies(page_url)
    for name in _CSRF_COOKIE_NAMES:
        cookie = cookies.get(name)
        if cookie is not None and cookie.value:
            return cookie.value
    return None


def _novapay_headers(csrf_token: str) -> dict[str, str]:
    """Headers observed on successful browser POST /api/check-otp and /api/payout."""
    return {
        "sec-ch-ua-platform": '"Windows"',
        "x-csrf-token": csrf_token,
        "Referer": "",
        "User-Agent": _BROWSER_UA,
        "sec-ch-ua": (
            '"Not;A=Brand";v="8", "Chromium";v="150", '
            '"Google Chrome";v="150"'
        ),
        "Content-Type": "application/json",
        "sec-ch-ua-mobile": "?0",
    }


async def _read_json(response: aiohttp.ClientResponse) -> Any:
    text = await response.text()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        msg = f"NovaPay returned non-JSON (HTTP {response.status}): {text[:300]}"
        raise NovaPoshtaApiError(msg) from exc


async def open_iframe_session(
    session: aiohttp.ClientSession,
    iframe_url: str,
) -> str:
    """GET payout widget page; return CSRF token when present (may be empty)."""
    logger.info("NovaPay iframe GET URL={}", iframe_url)
    async with session.get(
        iframe_url,
        headers={
            **_BROWSER_HEADERS,
            "Referer": "https://new.novaposhta.ua/",
            "Upgrade-Insecure-Requests": "1",
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "*/*;q=0.8"
            ),
        },
    ) as response:
        body = await response.text()
        logger.info("NovaPay iframe GET status={}", response.status)
        if response.status >= 400:
            msg = f"NovaPay iframe returned HTTP {response.status}"
            raise NovaPoshtaApiError(msg)

        csrf_token = _csrf_from_response(response) or _csrf_from_jar(
            session.cookie_jar,
            iframe_url,
        )
        if not csrf_token:
            # Current NovaPay builds expose CSRF in the page bootstrap script.
            for pattern in (
                r"window\.__CSRF_TOKEN__\s*=\s*'([^']+)'",
                r'window\.__CSRF_TOKEN__\s*=\s*"([^"]+)"',
                r'name=["\']csrf-token["\']\s+content=["\']([^"\']+)["\']',
                r'name=["\']_csrf["\']\s+value=["\']([^"\']+)["\']',
                r'"csrf(?:Token)?"\s*:\s*"([^"]+)"',
            ):
                match = re.search(pattern, body, flags=re.IGNORECASE)
                if match:
                    csrf_token = match.group(1).strip()
                    break

        session_cookie = response.cookies.get("pay-frontend-api-sid")
        if not csrf_token:
            jar_cookie = session.cookie_jar.filter_cookies(iframe_url).get(
                "pay-frontend-api-sid",
            )
            if session_cookie is None and jar_cookie is None:
                msg = "NovaPay iframe session did not provide session or CSRF cookie"
                raise NovaPoshtaApiError(msg)
            msg = (
                "NovaPay iframe opened but window.__CSRF_TOKEN__ was missing; "
                "POST /api/check-otp would return CorruptedRequestError"
            )
            raise NovaPoshtaApiError(msg)
        return csrf_token


async def _load_locales(session: aiohttp.ClientSession) -> None:
    """Browser loads /locales/uk.json after the payout page, before check-otp."""
    logger.info("NovaPay locales GET URL={}", LOCALES_UK_URL)
    async with session.get(
        LOCALES_UK_URL,
        headers={
            "User-Agent": _BROWSER_UA,
            "Referer": "",
        },
    ) as response:
        await response.read()
        logger.info("NovaPay locales GET status={}", response.status)
        if response.status >= 400:
            msg = f"NovaPay locales returned HTTP {response.status}"
            raise NovaPoshtaApiError(msg)


async def _call_check_otp(
    session: aiohttp.ClientSession,
    *,
    csrf_token: str,
    phone: str,
) -> dict[str, Any]:
    body = {
        "phone": _check_otp_phone(phone),
        "authorize": {"wallet": True},
    }
    headers = _novapay_headers(csrf_token)
    cookies = {
        name: morsel.value
        for name, morsel in session.cookie_jar.filter_cookies(NOVAPAY_ORIGIN).items()
    }
    logger.debug(
        "NovaPay check-otp request debug: url={} csrf_token={} body={} "
        "headers={} cookies={}",
        CHECK_OTP_URL,
        csrf_token,
        json.dumps(body, ensure_ascii=False),
        json.dumps(headers, ensure_ascii=False),
        json.dumps(cookies, ensure_ascii=False),
    )
    logger.info("NovaPay check-otp POST URL={} phone={}", CHECK_OTP_URL, body["phone"])
    async with session.post(
        CHECK_OTP_URL,
        json=body,
        headers=headers,
    ) as response:
        payload = await _read_json(response)
        logger.debug(
            "NovaPay check-otp response debug: status={} body={}",
            response.status,
            json.dumps(payload, ensure_ascii=False),
        )
        logger.info(
            "NovaPay check-otp status={} response={}",
            response.status,
            json.dumps(payload, ensure_ascii=False)[:1000],
        )
        if response.status >= 400:
            msg = f"NovaPay check-otp failed (HTTP {response.status})"
            raise NovaPoshtaApiError(msg)
        return payload if isinstance(payload, dict) else {}


async def _call_payout_api(
    session: aiohttp.ClientSession,
    *,
    csrf_token: str,
    payout_sid: str,
    pan: str,
) -> tuple[str, str]:
    url = f"{PAYOUT_API_URL}?sid={payout_sid}"
    body = {"pan": pan}
    logger.info(
        "NovaPay payout POST URL={} pan={}",
        url,
        mask_card_number(pan),
    )
    async with session.post(
        url,
        json=body,
        headers=_novapay_headers(csrf_token),
    ) as response:
        payload = await _read_json(response)
        logger.info(
            "NovaPay payout status={} response={}",
            response.status,
            json.dumps(payload, ensure_ascii=False)[:1000],
        )
        if response.status >= 400:
            errors = payload.get("errors") if isinstance(payload, dict) else None
            if isinstance(errors, list) and errors:
                message = str(errors[0].get("message") or errors[0])
            else:
                message = f"NovaPay payout failed (HTTP {response.status})"
            raise NovaPoshtaApiError(message)

        if not isinstance(payload, dict):
            msg = "NovaPay payout returned unexpected payload"
            raise NovaPoshtaApiError(msg)

        payout_id = str(payload.get("id") or "").strip()
        masked_pan = str(payload.get("pan") or "").strip()
        if not payout_id or not masked_pan:
            msg = "NovaPay payout response missing id or pan"
            raise NovaPoshtaApiError(msg)

        return payout_id, masked_pan


async def register_payout_card(
    client: NovaPoshtaClient,
    *,
    pan: str,
    phone: str,
    oauth_access_token: str,
    document_number: str | None = None,
    session: aiohttp.ClientSession | None = None,
) -> PayoutCardRegistration:
    """Run Payment.initPayout (TokenOAuth2) + observed NovaPay iframe API calls."""
    init_phone = _init_payout_phone(phone)
    logger.info(
        "Cash2Card initPayout request: Phone={} PAN={}",
        init_phone,
        mask_card_number(pan),
    )
    init_payload = await client.init_payout(
        phone=init_phone,
        oauth_access_token=oauth_access_token,
        document_number=document_number,
    )
    logger.info(
        "Cash2Card initPayout response: {}",
        json.dumps(init_payload, ensure_ascii=False),
    )

    init_url = str(init_payload.get("Url") or "").strip()
    init_id = str(init_payload.get("Id") or "").strip()
    int_doc_number = str(init_payload.get("IntDocNumber") or "").strip()
    if not init_url or not init_id or not int_doc_number:
        msg = "Payment.initPayout missing Url, Id, or IntDocNumber"
        raise NovaPoshtaApiError(msg)

    iframe_url = build_payout_iframe_url(init_url)
    owns_session = session is None
    if session is None:
        connector = aiohttp.TCPConnector(ssl=create_ssl_context())
        session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=60),
            cookie_jar=aiohttp.CookieJar(unsafe=True),
        )

    try:
        csrf_token = await open_iframe_session(session, iframe_url)
        await _load_locales(session)
        await _call_check_otp(session, csrf_token=csrf_token, phone=phone)
        payout_id, masked_pan = await _call_payout_api(
            session,
            csrf_token=csrf_token,
            payout_sid=init_id,
            pan=pan,
        )
        return PayoutCardRegistration(
            payout_id=payout_id,
            masked_pan=masked_pan,
            int_doc_number=int_doc_number,
            init_id=init_id,
            init_url=init_url,
        )
    finally:
        if owns_session and session is not None:
            await session.close()


async def register_card_via_payout_iframe(
    *,
    payout_url: str,
    payout_id: str,
    int_doc_number: str,
    pan: str,
    phone: str,
    session: aiohttp.ClientSession | None = None,
) -> PayoutCardRegistration:
    """Register card when initPayout was already performed."""
    iframe_url = build_payout_iframe_url(payout_url)
    owns_session = session is None
    if session is None:
        connector = aiohttp.TCPConnector(ssl=create_ssl_context())
        session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=60),
            cookie_jar=aiohttp.CookieJar(unsafe=True),
        )

    try:
        csrf_token = await open_iframe_session(session, iframe_url)
        await _load_locales(session)
        await _call_check_otp(session, csrf_token=csrf_token, phone=phone)
        registered_id, masked_pan = await _call_payout_api(
            session,
            csrf_token=csrf_token,
            payout_sid=payout_id,
            pan=pan,
        )
        return PayoutCardRegistration(
            payout_id=registered_id,
            masked_pan=masked_pan,
            int_doc_number=int_doc_number,
            init_id=payout_id,
            init_url=payout_url,
        )
    finally:
        if owns_session and session is not None:
            await session.close()
