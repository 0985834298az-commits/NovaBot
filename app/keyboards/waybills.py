from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.constants import (
    BTN_SYNC,
    BTN_WAYBILL_EDIT_PRODUCTS,
    CALLBACK_WAYBILL_EDIT_PRODUCTS,
    CALLBACK_WAYBILL_SYNC,
)


def build_waybill_actions_keyboard(waybill_id: int) -> InlineKeyboardMarkup:
    """Build inline actions for an active waybill."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_WAYBILL_EDIT_PRODUCTS,
        callback_data=f"{CALLBACK_WAYBILL_EDIT_PRODUCTS}:{waybill_id}",
    )
    return builder.as_markup()


def build_waybills_footer_keyboard() -> InlineKeyboardMarkup:
    """Build footer actions for the waybills list."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_SYNC, callback_data=CALLBACK_WAYBILL_SYNC)
    return builder.as_markup()
