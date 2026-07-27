from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.constants import (
    BTN_SETTINGS_TOGGLE_AUTO_SWITCH,
    CALLBACK_SETTINGS_TOGGLE_AUTO_SWITCH,
    MSG_SETTINGS_AUTO_SWITCH_OFF,
    MSG_SETTINGS_AUTO_SWITCH_ON,
)


def build_settings_keyboard(auto_account_switching: bool) -> InlineKeyboardMarkup:
    """Build bot settings keyboard."""
    status = MSG_SETTINGS_AUTO_SWITCH_ON if auto_account_switching else MSG_SETTINGS_AUTO_SWITCH_OFF
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"{BTN_SETTINGS_TOGGLE_AUTO_SWITCH}: {status}",
        callback_data=CALLBACK_SETTINGS_TOGGLE_AUTO_SWITCH,
    )
    return builder.as_markup()
