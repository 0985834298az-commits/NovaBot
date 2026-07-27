from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.nova_poshta_account import NovaPoshtaAccount


class NovaPoshtaAccountRepository:
    """Persistence layer for Nova Poshta API accounts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_account(
        self,
        *,
        telegram_user_id: int,
        account_name: str,
        api_key: str,
    ) -> NovaPoshtaAccount:
        """Create an account; the first account becomes active automatically."""
        existing_accounts = await self.get_all_accounts(telegram_user_id)
        account = NovaPoshtaAccount(
            telegram_user_id=telegram_user_id,
            account_name=account_name.strip(),
            api_key=api_key.strip(),
            is_active=not existing_accounts,
        )
        self._session.add(account)
        await self._session.flush()
        await self._session.refresh(account)
        return account

    async def get_all_accounts(self, telegram_user_id: int) -> list[NovaPoshtaAccount]:
        """Return all Nova Poshta accounts for a Telegram user."""
        result = await self._session.execute(
            select(NovaPoshtaAccount)
            .where(NovaPoshtaAccount.telegram_user_id == telegram_user_id)
            .order_by(NovaPoshtaAccount.is_active.desc(), NovaPoshtaAccount.id.asc()),
        )
        return list(result.scalars().all())

    async def get_by_id(
        self,
        account_id: int,
        telegram_user_id: int,
    ) -> NovaPoshtaAccount | None:
        """Return an account owned by the Telegram user."""
        result = await self._session.execute(
            select(NovaPoshtaAccount).where(
                NovaPoshtaAccount.id == account_id,
                NovaPoshtaAccount.telegram_user_id == telegram_user_id,
            ),
        )
        return result.scalar_one_or_none()

    async def get_active_account(self, telegram_user_id: int) -> NovaPoshtaAccount | None:
        """Return the active Nova Poshta account for a Telegram user."""
        result = await self._session.execute(
            select(NovaPoshtaAccount).where(
                NovaPoshtaAccount.telegram_user_id == telegram_user_id,
                NovaPoshtaAccount.is_active.is_(True),
            ),
        )
        return result.scalar_one_or_none()

    async def set_active_account(
        self,
        account_id: int,
        telegram_user_id: int,
    ) -> NovaPoshtaAccount | None:
        """Deactivate other accounts and mark the selected account as active."""
        account = await self.get_by_id(account_id, telegram_user_id)
        if account is None:
            return None

        await self._session.execute(
            update(NovaPoshtaAccount)
            .where(NovaPoshtaAccount.telegram_user_id == telegram_user_id)
            .values(is_active=False),
        )
        account.is_active = True
        await self._session.flush()
        await self._session.refresh(account)
        return account

    async def update_account(
        self,
        account_id: int,
        telegram_user_id: int,
        *,
        account_name: str | None = None,
        api_key: str | None = None,
    ) -> NovaPoshtaAccount | None:
        """Update account name and/or API key."""
        account = await self.get_by_id(account_id, telegram_user_id)
        if account is None:
            return None

        if account_name is not None:
            account.account_name = account_name.strip()
        if api_key is not None:
            account.api_key = api_key.strip()

        await self._session.flush()
        await self._session.refresh(account)
        return account

    async def delete_account(self, account_id: int, telegram_user_id: int) -> bool:
        """Delete an account and activate another one when needed."""
        account = await self.get_by_id(account_id, telegram_user_id)
        if account is None:
            return False

        was_active = account.is_active
        await self._session.delete(account)
        await self._session.flush()

        if was_active:
            remaining_accounts = await self.get_all_accounts(telegram_user_id)
            if remaining_accounts:
                await self.set_active_account(remaining_accounts[0].id, telegram_user_id)

        return True
