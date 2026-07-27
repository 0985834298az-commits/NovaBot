"""Helpers for parsing ordered product lines."""


def parse_product_lines(text: str) -> list[str]:
    """Parse non-empty product lines while preserving their order."""
    return [line.strip() for line in text.strip().splitlines() if line.strip()]
