"""Diagnostics logging for Nova Poshta payment card API responses."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from app.utils.payment_card import mask_card_number


def _normalize_digits(value: str | None) -> str:
    return "".join(char for char in str(value or "") if char.isdigit())


def extract_card_name(item: dict[str, Any]) -> str:
    for key in ("Name", "CardName", "Title", "Description"):
        value = str(item.get(key) or "").strip()
        if not value:
            continue
        digits = _normalize_digits(value)
        if len(digits) == 16 and digits == value.replace(" ", ""):
            continue
        return value
    return ""


def extract_card_ref(item: dict[str, Any]) -> str:
    for key in ("Ref", "PaymentCard", "PaymentCardRef", "CardRef"):
        ref = str(item.get(key) or "").strip()
        if ref:
            return ref
    return ""


def extract_card_number(item: dict[str, Any]) -> str:
    for key in (
        "Number",
        "CardNumber",
        "PaymentCardNumber",
        "Card",
        "Pan",
        "Description",
    ):
        digits = _normalize_digits(str(item.get(key) or ""))
        if len(digits) >= 4:
            return digits
    return ""


def extract_card_number_mask(item: dict[str, Any]) -> str:
    number = extract_card_number(item)
    if len(number) == 16:
        return mask_card_number(number)

    for key in ("Number", "CardNumber", "PaymentCardNumber", "Card", "Pan", "Description"):
        raw = str(item.get(key) or "").strip()
        if raw:
            return raw
    return ""


def _extract_card_items(response: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in response.get("data") or [] if isinstance(item, dict)]


def log_payment_cards_api_attempt(
    *,
    api_key_name: str,
    model_name: str,
    called_method: str,
    response: dict[str, Any],
) -> None:
    """Log Nova Poshta payment card API attempt details."""
    raw_response = json.dumps(response, ensure_ascii=False)
    logger.info("Nova Poshta payment cards load: api_key_name={}", api_key_name or "unknown")
    logger.info(
        "Nova Poshta payment cards load: model={} method={}",
        model_name,
        called_method,
    )
    logger.info("Nova Poshta payment cards load: raw_response={}", raw_response)

    items = _extract_card_items(response)
    if not items:
        logger.warning(
            "Nova Poshta payment cards load: zero cards returned "
            "(api_key_name={} model={} method={}) raw_response={}",
            api_key_name or "unknown",
            model_name,
            called_method,
            raw_response,
        )
        return

    for index, item in enumerate(items, start=1):
        logger.info(
            "Nova Poshta payment cards load: card[{}] ref={} number_mask={}",
            index,
            extract_card_ref(item) or "missing",
            extract_card_number_mask(item) or "missing",
        )


def log_payment_cards_lookup_failed(
    *,
    api_key_name: str,
    card_number: str,
    response: dict[str, Any],
) -> None:
    """Log diagnostics when a local card number cannot be matched."""
    masked_number = mask_card_number(card_number) if len(card_number) == 16 else card_number
    raw_response = json.dumps(response, ensure_ascii=False)
    items = _extract_card_items(response)

    if not items:
        logger.error(
            "Nova Poshta payment cards lookup failed: zero cards in final response "
            "(api_key_name={} requested_card={}) raw_response={}",
            api_key_name or "unknown",
            masked_number,
            raw_response,
        )
        return

    logger.error(
        "Nova Poshta payment cards lookup failed: no match for requested_card={} "
        "among {} card(s) (api_key_name={}) raw_response={}",
        masked_number,
        len(items),
        api_key_name or "unknown",
        raw_response,
    )
    for index, item in enumerate(items, start=1):
        logger.error(
            "Nova Poshta payment cards lookup failed: available_card[{}] ref={} number_mask={}",
            index,
            extract_card_ref(item) or "missing",
            extract_card_number_mask(item) or "missing",
        )
