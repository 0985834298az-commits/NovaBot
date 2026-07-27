from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.order_item_repository import OrderItemRepository
from app.repositories.payment_card_repository import PaymentCardRepository
from app.repositories.recipient_repository import RecipientRepository
from app.repositories.waybill_repository import WaybillRepository
from app.repositories.user_repository import UserRepository


class DatabaseMiddleware(BaseMiddleware):
    """Inject a database session and repositories into handler data."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self._session_factory() as session:
            data["session"] = session
            data["user_repository"] = UserRepository(session)
            data["recipient_repository"] = RecipientRepository(session)
            data["payment_card_repository"] = PaymentCardRepository(session)
            data["waybill_repository"] = WaybillRepository(session)
            data["order_item_repository"] = OrderItemRepository(session)
            data["nova_poshta_account_repository"] = NovaPoshtaAccountRepository(session)

            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
