from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.constants import (
    CALLBACK_SETTINGS_TOGGLE_AUTO_SWITCH,
    MSG_SETTINGS_AUTO_SWITCH,
    MSG_SETTINGS_AUTO_SWITCH_OFF,
    MSG_SETTINGS_AUTO_SWITCH_ON,
    MSG_SETTINGS_HEADER,
)
from app.keyboards import build_main_menu_keyboard, build_settings_keyboard
from app.repositories.user_repository import UserRepository

router = Router(name="settings")


async def show_settings(
    message: Message,
    user_repository: UserRepository,
) -> None:
    if message.from_user is None:
        return

    enabled = await user_repository.get_auto_account_switching(message.from_user.id)
    status = MSG_SETTINGS_AUTO_SWITCH_ON if enabled else MSG_SETTINGS_AUTO_SWITCH_OFF
    await message.answer(
        f"{MSG_SETTINGS_HEADER}\n\n{MSG_SETTINGS_AUTO_SWITCH}\n{status}",
        reply_markup=build_settings_keyboard(enabled),
    )


@router.callback_query(F.data == CALLBACK_SETTINGS_TOGGLE_AUTO_SWITCH)
async def handle_settings_toggle_auto_switch(
    callback: CallbackQuery,
    user_repository: UserRepository,
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    current = await user_repository.get_auto_account_switching(callback.from_user.id)
    enabled = await user_repository.set_auto_account_switching(
        callback.from_user.id,
        not current,
    )
    status = MSG_SETTINGS_AUTO_SWITCH_ON if enabled else MSG_SETTINGS_AUTO_SWITCH_OFF
    await callback.answer()
    await callback.message.answer(
        f"{MSG_SETTINGS_HEADER}\n\n{MSG_SETTINGS_AUTO_SWITCH}\n{status}",
        reply_markup=build_settings_keyboard(enabled),
    )
