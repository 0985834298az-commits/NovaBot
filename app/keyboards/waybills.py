from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.constants import BTN_WAYBILL_EDIT_PRODUCTS, CALLBACK_WAYBILL_EDIT_PRODUCTS


def build_waybill_actions_keyboard(waybill_id: int) -> InlineKeyboardMarkup:
    """Build inline actions for an active waybill."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_WAYBILL_EDIT_PRODUCTS,
        callback_data=f"{CALLBACK_WAYBILL_EDIT_PRODUCTS}:{waybill_id}",
    )
    return builder.as_markup()
