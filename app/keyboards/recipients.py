from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.constants import (
    BTN_RECIPIENT_CREATE_TTN,
    BTN_RECIPIENT_DELETE,
    BTN_RECIPIENT_DELETE_NO,
    BTN_RECIPIENT_DELETE_YES,
    BTN_RECIPIENT_EDIT,
    BTN_RECIPIENT_SEARCH,
    CALLBACK_RECIPIENT_DELETE,
    CALLBACK_RECIPIENT_DELETE_NO,
    CALLBACK_RECIPIENT_DELETE_YES,
    CALLBACK_RECIPIENT_EDIT,
    CALLBACK_RECIPIENT_SEARCH,
    CALLBACK_RECIPIENT_TTN,
)


def build_recipient_actions_keyboard(recipient_id: int) -> InlineKeyboardMarkup:
    """Build inline actions for a saved recipient."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_RECIPIENT_CREATE_TTN,
        callback_data=f"{CALLBACK_RECIPIENT_TTN}:{recipient_id}",
    )
    builder.button(
        text=BTN_RECIPIENT_EDIT,
        callback_data=f"{CALLBACK_RECIPIENT_EDIT}:{recipient_id}",
    )
    builder.button(
        text=BTN_RECIPIENT_DELETE,
        callback_data=f"{CALLBACK_RECIPIENT_DELETE}:{recipient_id}",
    )
    builder.adjust(1)
    return builder.as_markup()


def build_recipient_delete_keyboard(recipient_id: int) -> InlineKeyboardMarkup:
    """Build delete confirmation keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_RECIPIENT_DELETE_YES,
        callback_data=f"{CALLBACK_RECIPIENT_DELETE_YES}:{recipient_id}",
    )
    builder.button(
        text=BTN_RECIPIENT_DELETE_NO,
        callback_data=f"{CALLBACK_RECIPIENT_DELETE_NO}:{recipient_id}",
    )
    builder.adjust(2)
    return builder.as_markup()


def build_recipient_search_keyboard() -> InlineKeyboardMarkup:
    """Build search entry keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_RECIPIENT_SEARCH,
        callback_data=CALLBACK_RECIPIENT_SEARCH,
    )
    return builder.as_markup()
