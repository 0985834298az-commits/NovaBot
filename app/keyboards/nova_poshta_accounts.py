from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.constants import (
    BTN_BACK,
    BTN_NP_ACCOUNT_ACTIVATE,
    BTN_NP_ACCOUNT_ADD,
    BTN_NP_ACCOUNT_CHANGE_API,
    BTN_NP_ACCOUNT_DELETE,
    BTN_NP_ACCOUNT_DELETE_NO,
    BTN_NP_ACCOUNT_DELETE_YES,
    BTN_NP_ACCOUNT_OPEN,
    BTN_NP_ACCOUNT_RENAME,
    BTN_SYNC,
    CALLBACK_NP_ACCOUNT_ACTIVATE,
    CALLBACK_NP_ACCOUNT_ADD,
    CALLBACK_NP_ACCOUNT_BACK,
    CALLBACK_NP_ACCOUNT_CHANGE_API,
    CALLBACK_NP_ACCOUNT_DELETE,
    CALLBACK_NP_ACCOUNT_DELETE_NO,
    CALLBACK_NP_ACCOUNT_DELETE_YES,
    CALLBACK_NP_ACCOUNT_DETAIL_BACK,
    CALLBACK_NP_ACCOUNT_OPEN,
    CALLBACK_NP_ACCOUNT_RENAME,
    CALLBACK_NP_ACCOUNT_SYNC,
)


def build_nova_poshta_account_list_item_keyboard(account_id: int) -> InlineKeyboardMarkup:
    """Build open action for an account in the list."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_NP_ACCOUNT_OPEN,
        callback_data=f"{CALLBACK_NP_ACCOUNT_OPEN}:{account_id}",
    )
    return builder.as_markup()


def build_nova_poshta_account_detail_keyboard(account_id: int) -> InlineKeyboardMarkup:
    """Build actions for a selected Nova Poshta account."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_NP_ACCOUNT_CHANGE_API,
        callback_data=f"{CALLBACK_NP_ACCOUNT_CHANGE_API}:{account_id}",
    )
    builder.button(
        text=BTN_NP_ACCOUNT_RENAME,
        callback_data=f"{CALLBACK_NP_ACCOUNT_RENAME}:{account_id}",
    )
    builder.button(
        text=BTN_NP_ACCOUNT_ACTIVATE,
        callback_data=f"{CALLBACK_NP_ACCOUNT_ACTIVATE}:{account_id}",
    )
    builder.button(
        text=BTN_NP_ACCOUNT_DELETE,
        callback_data=f"{CALLBACK_NP_ACCOUNT_DELETE}:{account_id}",
    )
    builder.button(
        text=BTN_BACK,
        callback_data=CALLBACK_NP_ACCOUNT_DETAIL_BACK,
    )
    builder.adjust(1)
    return builder.as_markup()


def build_nova_poshta_accounts_footer_keyboard() -> InlineKeyboardMarkup:
    """Build footer actions for the accounts list."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_NP_ACCOUNT_ADD, callback_data=CALLBACK_NP_ACCOUNT_ADD)
    builder.button(text=BTN_SYNC, callback_data=CALLBACK_NP_ACCOUNT_SYNC)
    builder.button(text=BTN_BACK, callback_data=CALLBACK_NP_ACCOUNT_BACK)
    builder.adjust(1)
    return builder.as_markup()


def build_nova_poshta_account_delete_keyboard(account_id: int) -> InlineKeyboardMarkup:
    """Build delete confirmation keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_NP_ACCOUNT_DELETE_YES,
        callback_data=f"{CALLBACK_NP_ACCOUNT_DELETE_YES}:{account_id}",
    )
    builder.button(
        text=BTN_NP_ACCOUNT_DELETE_NO,
        callback_data=f"{CALLBACK_NP_ACCOUNT_DELETE_NO}:{account_id}",
    )
    builder.adjust(2)
    return builder.as_markup()
