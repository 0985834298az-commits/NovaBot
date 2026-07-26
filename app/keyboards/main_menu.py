from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from app.constants import (
    BTN_API_KEY,
    BTN_CARDS,
    BTN_CREATE_TTN,
    BTN_MY_WAYBILLS,
    BTN_RECIPIENTS,
    BTN_SETTINGS,
)


def build_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Build the main reply keyboard."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=BTN_CREATE_TTN),
        KeyboardButton(text=BTN_MY_WAYBILLS),
    )
    builder.row(
        KeyboardButton(text=BTN_RECIPIENTS),
        KeyboardButton(text=BTN_CARDS),
    )
    builder.row(
        KeyboardButton(text=BTN_API_KEY),
        KeyboardButton(text=BTN_SETTINGS),
    )
    return builder.as_markup(resize_keyboard=True)
