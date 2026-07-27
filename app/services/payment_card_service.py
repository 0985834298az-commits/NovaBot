"""Resolve Nova Poshta payment card references for COD payouts."""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.constants import MSG_CARD_NOT_FOUND_IN_NP, MSG_NO_ACTIVE_PAYMENT_CARD
from app.models.payment_card import PaymentCard
from app.nova_poshta import NovaPoshtaClient
from app.nova_poshta.exceptions import NovaPoshtaError
from app.repositories.payment_card_repository import PaymentCardRepository
from app.utils.payment_card_diagnostics import (
    extract_card_number,
    extract_card_ref,
    log_payment_cards_lookup_failed,
)


def _normalize_digits(value: str | None) -> str:
    return "".join(char for char in str(value or "") if char.isdigit())


def _extract_card_ref(item: dict[str, Any]) -> str:
    return extract_card_ref(item)


def _extract_card_number(item: dict[str, Any]) -> str:
    return extract_card_number(item)


def _cards_match(stored_number: str, remote_number: str) -> bool:
    if not stored_number or not remote_number:
        return False
    if stored_number == remote_number:
        return True
    return (
        len(stored_number) == 16
        and len(remote_number) >= 4
        and stored_number[:4] == remote_number[:4]
        and stored_number[-4:] == remote_number[-4:]
    )


def find_card_ref_in_response(
    response: dict[str, Any],
    card_number: str,
) -> str | None:
    """Find a Nova Poshta card Ref by card number."""
    normalized_number = _normalize_digits(card_number)
    if len(normalized_number) != 16:
        return None

    for item in response.get("data") or []:
        if not isinstance(item, dict):
            continue
        remote_number = _extract_card_number(item)
        if not _cards_match(normalized_number, remote_number):
            continue
        card_ref = _extract_card_ref(item)
        if card_ref:
            return card_ref
    return None


async def resolve_card_ref(
    client: NovaPoshtaClient,
    card_number: str,
    *,
    api_key_name: str = "",
) -> str:
    """Resolve Nova Poshta card Ref for a stored card number."""
    response = await client.get_payment_cards(api_key_name=api_key_name)
    card_ref = find_card_ref_in_response(response, card_number)
    if card_ref is None:
        log_payment_cards_lookup_failed(
            api_key_name=api_key_name,
            card_number=card_number,
            response=response,
        )
        raise NovaPoshtaError(MSG_CARD_NOT_FOUND_IN_NP)
    logger.info(
        "Nova Poshta payment cards lookup succeeded: api_key_name={} card_ref={}",
        api_key_name or "unknown",
        card_ref,
    )
    return card_ref


def is_active_card_ready(card: PaymentCard | None) -> bool:
    """Return True when the card can be used for COD TTN creation."""
    return card is not None and bool(card.card_ref.strip())


def apply_active_card_to_wizard(
    wizard_data: dict[str, Any],
    active_card: PaymentCard | None,
) -> None:
    """Attach the active card Ref to TTN wizard data."""
    if not is_active_card_ready(active_card):
        raise NovaPoshtaError(MSG_NO_ACTIVE_PAYMENT_CARD)

    assert active_card is not None
    wizard_data["payment_card_name"] = active_card.card_name
    wizard_data["payment_card_ref"] = active_card.card_ref.strip()
    wizard_data.pop("payment_card_number", None)


async def refresh_card_ref(
    *,
    card: PaymentCard,
    api_key: str,
    payment_card_repository: PaymentCardRepository,
    api_key_name: str = "",
) -> PaymentCard:
    """Refresh Nova Poshta card Ref for a stored card."""
    async with NovaPoshtaClient(api_key) as client:
        card_ref = await resolve_card_ref(
            client,
            card.card_number,
            api_key_name=api_key_name,
        )
    return await payment_card_repository.update_card_ref(card, card_ref=card_ref)


async def ensure_active_card_ref(
    *,
    active_card: PaymentCard,
    api_key: str,
    payment_card_repository: PaymentCardRepository,
    api_key_name: str = "",
) -> PaymentCard:
    """Ensure the active card has a Nova Poshta Ref before TTN creation."""
    if active_card.card_ref.strip():
        return active_card
    return await refresh_card_ref(
        card=active_card,
        api_key=api_key,
        payment_card_repository=payment_card_repository,
        api_key_name=api_key_name,
    )
