from __future__ import annotations

from datetime import timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    CALLBACK_SETTINGS_OAUTH_LOGIN,
    CALLBACK_SETTINGS_OAUTH_LOGOUT,
    CALLBACK_SETTINGS_OAUTH_REFRESH,
    CALLBACK_SETTINGS_TOGGLE_AUTO_SWITCH,
    MSG_SETTINGS_AUTO_SWITCH,
    MSG_SETTINGS_AUTO_SWITCH_OFF,
    MSG_SETTINGS_AUTO_SWITCH_ON,
    MSG_SETTINGS_HEADER,
    MSG_SETTINGS_OAUTH_CONNECTED,
    MSG_SETTINGS_OAUTH_DISCONNECTED,
    MSG_SETTINGS_OAUTH_EXPIRES,
    MSG_SETTINGS_OAUTH_HEADER,
    MSG_SETTINGS_OAUTH_LOGIN_BUSY,
    MSG_SETTINGS_OAUTH_LOGIN_FAIL,
    MSG_SETTINGS_OAUTH_LOGIN_OK,
    MSG_SETTINGS_OAUTH_LOGIN_START,
    MSG_SETTINGS_OAUTH_LOGOUT_EMPTY,
    MSG_SETTINGS_OAUTH_LOGOUT_OK,
)
from app.keyboards import build_settings_keyboard
from app.nova_poshta.oauth_browser_login import login_with_browser
from app.repositories.user_repository import UserRepository
from app.services.np_oauth_service import NpOAuthService, StoredOAuthTokens

router = Router(name="settings")

_oauth_login_in_progress: set[int] = set()


def _format_expires_at(tokens: StoredOAuthTokens) -> str:
    expires_at = tokens.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    local = expires_at.astimezone()
    return local.strftime("%d.%m.%Y %H:%M")


def _build_settings_text(
    *,
    auto_account_switching: bool,
    oauth_tokens: StoredOAuthTokens | None,
) -> str:
    auto_status = (
        MSG_SETTINGS_AUTO_SWITCH_ON
        if auto_account_switching
        else MSG_SETTINGS_AUTO_SWITCH_OFF
    )
    lines = [
        MSG_SETTINGS_HEADER,
        "",
        MSG_SETTINGS_AUTO_SWITCH,
        auto_status,
        "",
        MSG_SETTINGS_OAUTH_HEADER,
    ]
    if oauth_tokens is None:
        lines.append(MSG_SETTINGS_OAUTH_DISCONNECTED)
    else:
        lines.append(MSG_SETTINGS_OAUTH_CONNECTED)
        lines.append(
            MSG_SETTINGS_OAUTH_EXPIRES.format(
                expires_at=_format_expires_at(oauth_tokens),
            ),
        )
    return "\n".join(lines)


async def show_settings(
    message: Message,
    user_repository: UserRepository,
    session: AsyncSession,
) -> None:
    if message.from_user is None:
        return

    enabled = await user_repository.get_auto_account_switching(message.from_user.id)
    oauth_tokens = await NpOAuthService(session).load_tokens(message.from_user.id)
    await message.answer(
        _build_settings_text(
            auto_account_switching=enabled,
            oauth_tokens=oauth_tokens,
        ),
        reply_markup=build_settings_keyboard(
            enabled,
            oauth_connected=oauth_tokens is not None,
        ),
    )


async def _reply_settings(
    message: Message,
    *,
    telegram_user_id: int,
    user_repository: UserRepository,
    session: AsyncSession,
) -> None:
    enabled = await user_repository.get_auto_account_switching(telegram_user_id)
    oauth_tokens = await NpOAuthService(session).load_tokens(telegram_user_id)
    await message.answer(
        _build_settings_text(
            auto_account_switching=enabled,
            oauth_tokens=oauth_tokens,
        ),
        reply_markup=build_settings_keyboard(
            enabled,
            oauth_connected=oauth_tokens is not None,
        ),
    )


@router.callback_query(F.data == CALLBACK_SETTINGS_TOGGLE_AUTO_SWITCH)
async def handle_settings_toggle_auto_switch(
    callback: CallbackQuery,
    user_repository: UserRepository,
    session: AsyncSession,
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    current = await user_repository.get_auto_account_switching(callback.from_user.id)
    await user_repository.set_auto_account_switching(
        callback.from_user.id,
        not current,
    )
    await callback.answer()
    await _reply_settings(
        callback.message,
        telegram_user_id=callback.from_user.id,
        user_repository=user_repository,
        session=session,
    )


@router.callback_query(F.data == CALLBACK_SETTINGS_OAUTH_REFRESH)
async def handle_settings_oauth_refresh(
    callback: CallbackQuery,
    user_repository: UserRepository,
    session: AsyncSession,
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    await callback.answer()
    await _reply_settings(
        callback.message,
        telegram_user_id=callback.from_user.id,
        user_repository=user_repository,
        session=session,
    )


@router.callback_query(F.data == CALLBACK_SETTINGS_OAUTH_LOGIN)
async def handle_settings_oauth_login(
    callback: CallbackQuery,
    user_repository: UserRepository,
    session: AsyncSession,
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    user_id = callback.from_user.id
    if user_id in _oauth_login_in_progress:
        await callback.answer(MSG_SETTINGS_OAUTH_LOGIN_BUSY, show_alert=True)
        return

    await callback.answer()
    _oauth_login_in_progress.add(user_id)
    await callback.message.answer(MSG_SETTINGS_OAUTH_LOGIN_START)
    try:
        result = await login_with_browser(headless=False)
        oauth = NpOAuthService(session)
        stored = await oauth.save_tokens(user_id, result.tokens)
        await callback.message.answer(
            MSG_SETTINGS_OAUTH_LOGIN_OK.format(
                expires_at=_format_expires_at(stored),
            ),
        )
        logger.info("OAuth login via Settings succeeded for user {}", user_id)
    except Exception as exc:
        logger.exception("OAuth login via Settings failed for user {}", user_id)
        await callback.message.answer(
            MSG_SETTINGS_OAUTH_LOGIN_FAIL.format(error=str(exc)),
        )
    finally:
        _oauth_login_in_progress.discard(user_id)

    await _reply_settings(
        callback.message,
        telegram_user_id=user_id,
        user_repository=user_repository,
        session=session,
    )


@router.callback_query(F.data == CALLBACK_SETTINGS_OAUTH_LOGOUT)
async def handle_settings_oauth_logout(
    callback: CallbackQuery,
    user_repository: UserRepository,
    session: AsyncSession,
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    deleted = await NpOAuthService(session).clear_tokens(callback.from_user.id)
    await callback.answer()
    await callback.message.answer(
        MSG_SETTINGS_OAUTH_LOGOUT_OK if deleted else MSG_SETTINGS_OAUTH_LOGOUT_EMPTY,
    )
    await _reply_settings(
        callback.message,
        telegram_user_id=callback.from_user.id,
        user_repository=user_repository,
        session=session,
    )
