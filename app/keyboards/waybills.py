from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.constants import (
    BTN_WAYBILL_DELETE,
    BTN_WAYBILL_DELETE_NO,
    BTN_WAYBILL_DELETE_YES,
    BTN_WAYBILL_EDIT_PRODUCTS,
    CALLBACK_WAYBILL_DELETE,
    CALLBACK_WAYBILL_DELETE_NO,
    CALLBACK_WAYBILL_DELETE_YES,
    CALLBACK_WAYBILL_EDIT_PRODUCTS,
)


def build_waybill_actions_keyboard(waybill_id: int) -> InlineKeyboardMarkup:
    """Build inline actions for an active waybill."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_WAYBILL_EDIT_PRODUCTS,
        callback_data=f"{CALLBACK_WAYBILL_EDIT_PRODUCTS}:{waybill_id}",
    )
    builder.button(
        text=BTN_WAYBILL_DELETE,
        callback_data=f"{CALLBACK_WAYBILL_DELETE}:{waybill_id}",
    )
    builder.adjust(1)
    return builder.as_markup()


def build_waybill_delete_keyboard(waybill_id: int) -> InlineKeyboardMarkup:
    """Build delete confirmation keyboard for a waybill."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_WAYBILL_DELETE_YES,
        callback_data=f"{CALLBACK_WAYBILL_DELETE_YES}:{waybill_id}",
    )
    builder.button(
        text=BTN_WAYBILL_DELETE_NO,
        callback_data=f"{CALLBACK_WAYBILL_DELETE_NO}:{waybill_id}",
    )
    builder.adjust(2)
    return builder.as_markup()
