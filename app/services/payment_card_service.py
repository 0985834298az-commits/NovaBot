"""Local payment card storage and Nova Poshta card import."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.constants import MSG_NO_ACTIVE_PAYMENT_CARD
from app.models.payment_card import PaymentCard
from app.nova_poshta import NovaPoshtaClient
from app.nova_poshta.exceptions import NovaPoshtaError
from app.repositories.payment_card_repository import PaymentCardRepository
from app.utils.payment_card import mask_card_number
from app.utils.payment_card_diagnostics import (
    extract_card_name,
    extract_card_number,
    extract_card_number_mask,
    extract_card_ref,
)


def _normalize_digits(value: str | None) -> str:
    return "".join(char for char in str(value or "") if char.isdigit())


def _extract_card_items(response: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in response.get("data") or [] if isinstance(item, dict)]


def parse_imported_payment_card(item: dict[str, Any]) -> dict[str, str] | None:
    """Parse one Nova Poshta payment card payload into local fields."""
    card_ref = extract_card_ref(item)
    card_number = extract_card_number(item)
    masked_number = extract_card_number_mask(item)
    card_name = extract_card_name(item)

    if not card_ref and len(card_number) != 16:
        return None

    if not card_name:
        card_name = masked_number or "Картка Nova Poshta"

    if not masked_number and len(card_number) == 16:
        masked_number = mask_card_number(card_number)

    owner_name = card_name
    if len(card_number) != 16:
        digits = _normalize_digits(masked_number)
        card_number = digits if len(digits) == 16 else card_number

    return {
        "card_name": card_name.strip(),
        "card_ref": card_ref.strip(),
        "masked_number": masked_number.strip(),
        "owner_name": owner_name.strip(),
        "card_number": card_number,
    }


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


async def import_payment_cards_from_nova_poshta(
    *,
    telegram_user_id: int,
    api_key: str,
    payment_card_repository: PaymentCardRepository,
    api_key_name: str = "",
) -> int:
    """Import all payment cards from Nova Poshta into the local database."""
    async with NovaPoshtaClient(api_key) as client:
        response = await client.get_payment_cards(api_key_name=api_key_name)

    items = _extract_card_items(response)
    if not items:
        return 0

    imported_at = datetime.now(timezone.utc)
    imported_count = 0

    for item in items:
        parsed = parse_imported_payment_card(item)
        if parsed is None:
            continue

        await payment_card_repository.upsert_imported_card(
            telegram_user_id=telegram_user_id,
            imported_at=imported_at,
            **parsed,
        )
        imported_count += 1

    logger.info(
        "Imported {} payment card(s) for user {} (api_key_name={})",
        imported_count,
        telegram_user_id,
        api_key_name or "unknown",
    )
    return imported_count
