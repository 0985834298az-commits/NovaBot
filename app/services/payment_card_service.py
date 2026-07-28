"""Local payment card storage for Cash2Card TTN creation."""

from __future__ import annotations

from typing import Any

from app.constants import MSG_NO_ACTIVE_PAYMENT_CARD
from app.models.payment_card import PaymentCard
from app.nova_poshta.exceptions import NovaPoshtaError
from app.utils.payment_card import validate_card_number


def is_active_card_ready(card: PaymentCard | None) -> bool:
    """Return True when the card has a valid PAN for Cash2Card TTN creation."""
    if card is None:
        return False
    return validate_card_number(card.card_number) is not None


def apply_active_card_to_wizard(
    wizard_data: dict[str, Any],
    active_card: PaymentCard | None,
) -> None:
    """Attach the active card PAN to TTN wizard data."""
    if not is_active_card_ready(active_card):
        raise NovaPoshtaError(MSG_NO_ACTIVE_PAYMENT_CARD)

    assert active_card is not None
    wizard_data["payment_card_name"] = active_card.card_name
    wizard_data["payment_card_number"] = active_card.card_number.strip()
    wizard_data.pop("payment_card_ref", None)
