from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Persistence layer for Telegram users."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user(self, telegram_id: int) -> User | None:
        """Return a user by Telegram ID."""
        result = await self._session.execute(
            select(User).where(User.telegram_id == telegram_id),
        )
        return result.scalar_one_or_none()

    async def create_user(self, telegram_id: int) -> User:
        """Create a new user record."""
        user = User(telegram_id=telegram_id)
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def get_or_create_user(self, telegram_id: int) -> User:
        """Return an existing user or create a new one."""
        user = await self.get_user(telegram_id)
        if user is None:
            user = await self.create_user(telegram_id)
        return user

    async def get_auto_account_switching(self, telegram_id: int) -> bool:
        """Return whether automatic NP account switching is enabled."""
        user = await self.get_or_create_user(telegram_id)
        return bool(user.auto_account_switching)

    async def set_auto_account_switching(
        self,
        telegram_id: int,
        enabled: bool,
    ) -> bool:
        """Enable or disable automatic NP account switching."""
        user = await self.get_or_create_user(telegram_id)
        user.auto_account_switching = enabled
        await self._session.flush()
        await self._session.refresh(user)
        return user.auto_account_switching
