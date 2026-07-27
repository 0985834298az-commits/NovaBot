from __future__ import annotations

from decimal import Decimal, InvalidOperation


def parse_cod_amount(value: str | float | int | Decimal) -> Decimal:
    """Parse a COD amount into a non-negative decimal."""
    if isinstance(value, Decimal):
        amount = value
    else:
        normalized = str(value).strip().replace(",", ".")
        if not normalized:
            return Decimal(0)
        try:
            amount = Decimal(normalized)
        except InvalidOperation as exc:
            msg = f"Invalid COD amount: {value!r}"
            raise ValueError(msg) from exc

    if amount < 0:
        msg = f"COD amount must be non-negative: {value!r}"
        raise ValueError(msg)
    return amount


def format_money_uah(amount: Decimal | float | int | str) -> str:
    """Format an amount as Ukrainian hryvnia text."""
    value = parse_cod_amount(amount)
    normalized = int(value) if value == value.to_integral_value() else float(value)
    if isinstance(normalized, float):
        text = f"{normalized:,.2f}".replace(",", " ").replace(".", ",")
    else:
        text = f"{normalized:,}".replace(",", " ")
    return f"{text} грн"
