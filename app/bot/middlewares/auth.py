from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from app.constants import UNAUTHORIZED_MESSAGE


class AuthorizationMiddleware(BaseMiddleware):
    """Allow only Telegram users listed in ADMIN_IDS."""

    def __init__(self, admin_ids: frozenset[int]) -> None:
        self._admin_ids = admin_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is not None and user.id in self._admin_ids:
            return await handler(event, data)

        await self._reject_access(event, data.get("bot"))
        return None

    async def _reject_access(
        self,
        event: TelegramObject,
        bot: Bot | None,
    ) -> None:
        if isinstance(event, Message):
            await event.answer(UNAUTHORIZED_MESSAGE)
            return

        if isinstance(event, CallbackQuery):
            await event.answer(UNAUTHORIZED_MESSAGE, show_alert=True)
            if event.message is not None:
                await event.message.answer(UNAUTHORIZED_MESSAGE)
            return

        if isinstance(event, Update):
            if event.message is not None:
                await event.message.answer(UNAUTHORIZED_MESSAGE)
                return

            if event.callback_query is not None:
                await event.callback_query.answer(
                    UNAUTHORIZED_MESSAGE,
                    show_alert=True,
                )
                if event.callback_query.message is not None:
                    await event.callback_query.message.answer(UNAUTHORIZED_MESSAGE)
                return

            if event.edited_message is not None:
                await event.edited_message.answer(UNAUTHORIZED_MESSAGE)
                return

            if bot is not None and event.inline_query is not None:
                await bot.send_message(
                    chat_id=event.inline_query.from_user.id,
                    text=UNAUTHORIZED_MESSAGE,
                )
