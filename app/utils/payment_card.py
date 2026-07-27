"""Helpers for payment card display and validation."""


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
    card_name = getattr(card, "card_name", None) or card.owner_name
    return (
        f"{indicator} {card_name}\n"
        f"{card.owner_name}\n"
        f"{mask_card_number(card.card_number)}"
    )
