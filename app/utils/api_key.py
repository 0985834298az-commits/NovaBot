from app.constants import API_KEY_MASK_SUFFIX


def mask_api_key(api_key: str, visible_chars: int = 8) -> str:
    """Return the first characters of an API key followed by a mask."""
    prefix = api_key[:visible_chars]
    return f"{prefix}{API_KEY_MASK_SUFFIX}"
