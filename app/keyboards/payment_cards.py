from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.constants import (
    BTN_BACK,
    BTN_CARD_ADD,
    BTN_CARD_DELETE,
    BTN_CARD_DELETE_NO,
    BTN_CARD_DELETE_YES,
    BTN_CARD_EDIT,
    BTN_CARD_SELECT,
    CALLBACK_CARD_ADD,
    CALLBACK_CARD_BACK,
    CALLBACK_CARD_DELETE,
    CALLBACK_CARD_DELETE_NO,
    CALLBACK_CARD_DELETE_YES,
    CALLBACK_CARD_EDIT,
    CALLBACK_CARD_SELECT,
)


def build_payment_card_actions_keyboard(card_id: int) -> InlineKeyboardMarkup:
    """Build inline actions for a saved payment card."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_CARD_SELECT,
        callback_data=f"{CALLBACK_CARD_SELECT}:{card_id}",
    )
    builder.button(
        text=BTN_CARD_EDIT,
        callback_data=f"{CALLBACK_CARD_EDIT}:{card_id}",
    )
    builder.button(
        text=BTN_CARD_DELETE,
        callback_data=f"{CALLBACK_CARD_DELETE}:{card_id}",
    )
    builder.adjust(3)
    return builder.as_markup()


def build_payment_cards_footer_keyboard() -> InlineKeyboardMarkup:
    """Build footer actions for the payment cards list."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_CARD_ADD, callback_data=CALLBACK_CARD_ADD)
    builder.button(text=BTN_BACK, callback_data=CALLBACK_CARD_BACK)
    builder.adjust(1, 1)
    return builder.as_markup()


def build_payment_card_delete_keyboard(card_id: int) -> InlineKeyboardMarkup:
    """Build delete confirmation keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_CARD_DELETE_YES,
        callback_data=f"{CALLBACK_CARD_DELETE_YES}:{card_id}",
    )
    builder.button(
        text=BTN_CARD_DELETE_NO,
        callback_data=f"{CALLBACK_CARD_DELETE_NO}:{card_id}",
    )
    builder.adjust(2)
    return builder.as_markup()
