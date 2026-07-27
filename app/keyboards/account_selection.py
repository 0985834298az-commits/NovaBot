from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.constants import (
    BTN_ACCOUNT_SEL_CANCEL,
    BTN_ACCOUNT_SEL_CREATE_ANYWAY,
    BTN_ACCOUNT_SEL_SELECT,
    CALLBACK_ACCOUNT_SEL_CANCEL,
    CALLBACK_ACCOUNT_SEL_CREATE_ANYWAY,
    CALLBACK_ACCOUNT_SEL_PICK,
    CALLBACK_ACCOUNT_SEL_SELECT,
)
from app.services.account_selection_service import AccountUsageInfo


def build_account_limit_keyboard() -> InlineKeyboardMarkup:
    """Build actions when no account has enough monthly limit."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_ACCOUNT_SEL_CREATE_ANYWAY,
        callback_data=CALLBACK_ACCOUNT_SEL_CREATE_ANYWAY,
    )
    builder.button(
        text=BTN_ACCOUNT_SEL_SELECT,
        callback_data=CALLBACK_ACCOUNT_SEL_SELECT,
    )
    builder.button(
        text=BTN_ACCOUNT_SEL_CANCEL,
        callback_data=CALLBACK_ACCOUNT_SEL_CANCEL,
    )
    builder.adjust(1)
    return builder.as_markup()


def build_account_pick_keyboard(usages: list[AccountUsageInfo]) -> InlineKeyboardMarkup:
    """Build manual account selection keyboard with usage stats."""
    builder = InlineKeyboardBuilder()
    for usage in usages:
        indicator = "🟢" if usage.account.is_active else "⚪️"
        builder.button(
            text=f"{indicator} {usage.account.account_name}",
            callback_data=f"{CALLBACK_ACCOUNT_SEL_PICK}:{usage.account.id}",
        )
    builder.button(
        text=BTN_ACCOUNT_SEL_CANCEL,
        callback_data=CALLBACK_ACCOUNT_SEL_CANCEL,
    )
    builder.adjust(1)
    return builder.as_markup()
