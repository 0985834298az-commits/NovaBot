from app.models.nova_poshta_account import NovaPoshtaAccount
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.services.sender_cache import (
    ensure_sender_cache,
    get_cached_sender_location,
    get_sender_cache_error,
)


def format_nova_poshta_account(account: NovaPoshtaAccount) -> str:
    """Format a Nova Poshta account for Telegram display."""
    indicator = "🟢" if account.is_active else "⚪️"
    return f"{indicator} {account.account_name}"


async def get_active_api_key(
    account_repository: NovaPoshtaAccountRepository,
    telegram_user_id: int,
) -> str | None:
    """Return the active Nova Poshta API key for a Telegram user."""
    account = await account_repository.get_active_account(telegram_user_id)
    if account is None:
        return None
    return account.api_key


async def ensure_active_account_sender_cache(
    account_repository: NovaPoshtaAccountRepository,
    telegram_user_id: int,
) -> tuple[str, dict[str, dict[str, str]]] | None:
    """Load the active account and ensure sender refs are cached for the user."""
    account = await account_repository.get_active_account(telegram_user_id)
    if account is None:
        return None

    if not await ensure_sender_cache(telegram_user_id, account.api_key):
        error = get_sender_cache_error(telegram_user_id) or "Sender location is not configured"
        raise RuntimeError(error)

    return account.api_key, get_cached_sender_location(telegram_user_id)
