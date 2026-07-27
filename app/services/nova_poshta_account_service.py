from app.models.nova_poshta_account import NovaPoshtaAccount
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository


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
