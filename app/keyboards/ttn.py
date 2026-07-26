from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.constants import (
    BTN_TTN_CANCEL,
    BTN_TTN_CREATE,
    BTN_TTN_EDIT,
    CALLBACK_TTN_CITY,
    CALLBACK_TTN_EDIT_FIELD,
    CALLBACK_TTN_REVIEW_CANCEL,
    CALLBACK_TTN_REVIEW_CREATE,
    CALLBACK_TTN_REVIEW_EDIT,
    CALLBACK_TTN_WAREHOUSE,
    TTN_EDIT_FIELDS,
)


def build_city_keyboard(
    items: list[dict[str, str]],
    *,
    side: str,
) -> InlineKeyboardMarkup:
    """Build inline keyboard for settlement selection."""
    builder = InlineKeyboardBuilder()
    for item in items[:10]:
        city_ref = item["ref"]
        builder.button(
            text=item["name"][:64],
            callback_data=f"{CALLBACK_TTN_CITY}:{side}:{city_ref}",
        )
    builder.adjust(1)
    return builder.as_markup()


def build_warehouse_keyboard(
    items: list[dict[str, str]],
    *,
    side: str,
) -> InlineKeyboardMarkup:
    """Build inline keyboard for warehouse selection."""
    builder = InlineKeyboardBuilder()
    for index, item in enumerate(items[:10]):
        label = item["description"] or f"№{item['number']}"
        builder.button(
            text=label[:64],
            callback_data=f"{CALLBACK_TTN_WAREHOUSE}:{side}:{index}",
        )
    builder.adjust(1)
    return builder.as_markup()


def build_review_keyboard() -> InlineKeyboardMarkup:
    """Build review step action keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_TTN_CREATE, callback_data=CALLBACK_TTN_REVIEW_CREATE)
    builder.button(text=BTN_TTN_EDIT, callback_data=CALLBACK_TTN_REVIEW_EDIT)
    builder.button(text=BTN_TTN_CANCEL, callback_data=CALLBACK_TTN_REVIEW_CANCEL)
    builder.adjust(1)
    return builder.as_markup()


def build_edit_fields_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for selecting a field to edit."""
    builder = InlineKeyboardBuilder()
    for field_key, (label, _) in TTN_EDIT_FIELDS.items():
        builder.button(
            text=label,
            callback_data=f"{CALLBACK_TTN_EDIT_FIELD}:{field_key}",
        )
    builder.adjust(1)
    return builder.as_markup()
