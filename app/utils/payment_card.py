"""Helpers for payment card display and validation."""

from app.constants import MSG_CARD_REF_AVAILABLE, MSG_CARD_REF_MISSING


def mask_card_number(card_number: str) -> str:
    """Mask a card number as 4441 ** ** 3333."""
    digits = "".join(char for char in card_number if char.isdigit())
    if len(digits) != 16:
        return card_number
    return f"{digits[:4]} ** ** {digits[-4:]}"


def validate_card_number(value: str) -> str | None:
    """Return normalized 16-digit card number or None when invalid."""
    digits = "".join(char for char in value if char.isdigit())
    if len(digits) == 16:
        return digits
    return None


def format_payment_card(card: object) -> str:
    """Format a payment card for Telegram display."""
    indicator = "🟢" if card.is_active else "⚪️"
    card_name = getattr(card, "card_name", None) or getattr(card, "owner_name", "")
    masked_number = getattr(card, "masked_number", None) or mask_card_number(card.card_number)
    ref_status = (
        MSG_CARD_REF_AVAILABLE
        if str(getattr(card, "card_ref", "") or "").strip()
        else MSG_CARD_REF_MISSING
    )
    return f"{indicator} {card_name}\n{masked_number}\n{ref_status}"
