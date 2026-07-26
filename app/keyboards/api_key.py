from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.constants import BTN_REPLACE_API_KEY, CALLBACK_REPLACE_API_KEY


def build_replace_api_key_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard for replacing the stored API key."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_REPLACE_API_KEY,
        callback_data=CALLBACK_REPLACE_API_KEY,
    )
    return builder.as_markup()
