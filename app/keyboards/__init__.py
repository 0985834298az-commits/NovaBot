"""Telegram keyboards."""

from app.keyboards.account_selection import (
    build_account_limit_keyboard,
    build_account_pick_keyboard,
)
from app.keyboards.main_menu import build_main_menu_keyboard
from app.keyboards.nova_poshta_accounts import (
    build_nova_poshta_account_delete_keyboard,
    build_nova_poshta_account_detail_keyboard,
    build_nova_poshta_account_list_item_keyboard,
    build_nova_poshta_accounts_footer_keyboard,
)
from app.keyboards.payment_cards import (
    build_payment_card_actions_keyboard,
    build_payment_card_delete_keyboard,
    build_payment_cards_footer_keyboard,
)
from app.keyboards.recipients import (
    build_recipient_actions_keyboard,
    build_recipient_delete_keyboard,
    build_recipient_search_keyboard,
)
from app.keyboards.settings import build_settings_keyboard
from app.keyboards.waybills import (
    build_waybill_actions_keyboard,
    build_waybills_footer_keyboard,
)

__all__ = (
    "build_account_limit_keyboard",
    "build_account_pick_keyboard",
    "build_main_menu_keyboard",
    "build_nova_poshta_account_delete_keyboard",
    "build_nova_poshta_account_detail_keyboard",
    "build_nova_poshta_account_list_item_keyboard",
    "build_nova_poshta_accounts_footer_keyboard",
    "build_payment_card_actions_keyboard",
    "build_payment_card_delete_keyboard",
    "build_payment_cards_footer_keyboard",
    "build_recipient_actions_keyboard",
    "build_recipient_delete_keyboard",
    "build_recipient_search_keyboard",
    "build_settings_keyboard",
    "build_waybill_actions_keyboard",
    "build_waybills_footer_keyboard",
)
