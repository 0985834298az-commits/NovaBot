from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Persistence layer for Telegram users and API keys."""

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

    async def save_api_key(self, telegram_id: int, api_key: str) -> User:
        """Create or update a user's Nova Poshta API key."""
        user = await self.get_user(telegram_id)
        if user is None:
            user = await self.create_user(telegram_id)

        user.api_key = api_key.strip()
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def get_or_create_user(self, telegram_id: int) -> User:
        """Return an existing user or create a new one."""
        user = await self.get_user(telegram_id)
        if user is None:
            user = await self.create_user(telegram_id)
        return user

    async def get_any_api_key(self) -> str | None:
        """Return any stored Nova Poshta API key."""
        result = await self._session.execute(
            select(User.api_key)
            .where(User.api_key.is_not(None))
            .where(User.api_key != "")
            .limit(1),
        )
        api_key = result.scalar_one_or_none()
        if api_key is None:
            return None
        return str(api_key).strip() or None
