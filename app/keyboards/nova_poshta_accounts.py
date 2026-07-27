from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.constants import (
    BTN_BACK,
    BTN_NP_ACCOUNT_ADD,
    BTN_NP_ACCOUNT_CHANGE_API,
    BTN_NP_ACCOUNT_DELETE,
    BTN_NP_ACCOUNT_DELETE_NO,
    BTN_NP_ACCOUNT_DELETE_YES,
    BTN_NP_ACCOUNT_RENAME,
    BTN_NP_ACCOUNT_SELECT,
    CALLBACK_NP_ACCOUNT_ADD,
    CALLBACK_NP_ACCOUNT_BACK,
    CALLBACK_NP_ACCOUNT_CHANGE_API,
    CALLBACK_NP_ACCOUNT_DELETE,
    CALLBACK_NP_ACCOUNT_DELETE_NO,
    CALLBACK_NP_ACCOUNT_DELETE_YES,
    CALLBACK_NP_ACCOUNT_RENAME,
    CALLBACK_NP_ACCOUNT_SELECT,
)


def build_nova_poshta_account_actions_keyboard(account_id: int) -> InlineKeyboardMarkup:
    """Build inline actions for a saved Nova Poshta account."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_NP_ACCOUNT_SELECT,
        callback_data=f"{CALLBACK_NP_ACCOUNT_SELECT}:{account_id}",
    )
    builder.button(
        text=BTN_NP_ACCOUNT_RENAME,
        callback_data=f"{CALLBACK_NP_ACCOUNT_RENAME}:{account_id}",
    )
    builder.button(
        text=BTN_NP_ACCOUNT_CHANGE_API,
        callback_data=f"{CALLBACK_NP_ACCOUNT_CHANGE_API}:{account_id}",
    )
    builder.button(
        text=BTN_NP_ACCOUNT_DELETE,
        callback_data=f"{CALLBACK_NP_ACCOUNT_DELETE}:{account_id}",
    )
    builder.adjust(2, 2)
    return builder.as_markup()


def build_nova_poshta_accounts_footer_keyboard() -> InlineKeyboardMarkup:
    """Build footer actions for the accounts list."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_NP_ACCOUNT_ADD, callback_data=CALLBACK_NP_ACCOUNT_ADD)
    builder.button(text=BTN_BACK, callback_data=CALLBACK_NP_ACCOUNT_BACK)
    builder.adjust(2)
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
