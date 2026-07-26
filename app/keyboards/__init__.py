"""Telegram keyboards."""

from app.keyboards.api_key import build_replace_api_key_keyboard
from app.keyboards.main_menu import build_main_menu_keyboard
from app.keyboards.recipients import (
    build_recipient_actions_keyboard,
    build_recipient_delete_keyboard,
    build_recipient_search_keyboard,
)

__all__ = (
    "build_main_menu_keyboard",
    "build_recipient_actions_keyboard",
    "build_recipient_delete_keyboard",
    "build_recipient_search_keyboard",
    "build_replace_api_key_keyboard",
)
