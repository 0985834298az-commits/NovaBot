from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.constants import (
    ASK_API_KEY_MESSAGE,
    BTN_API_KEY,
    BTN_CREATE_TTN,
    BTN_MY_WAYBILLS,
    BTN_RECIPIENTS,
    BTN_SETTINGS,
    MSG_CREATE_TTN_SOON,
    MSG_RECIPIENTS_EMPTY,
    MSG_SETTINGS_SOON,
    MSG_WAYBILLS_EMPTY,
    API_KEY_VISIBLE_CHARS,
)
from app.handlers.states import WaitingForApiKey
from app.keyboards import build_main_menu_keyboard, build_replace_api_key_keyboard
from app.repositories.user_repository import UserRepository
from app.utils.api_key import mask_api_key

router = Router(name="menu")


@router.message(F.text == BTN_CREATE_TTN, StateFilter(None))
async def handle_create_ttn(message: Message) -> None:
    """Placeholder for TTN creation."""
    await message.answer(
        MSG_CREATE_TTN_SOON,
        reply_markup=build_main_menu_keyboard(),
    )


@router.message(F.text == BTN_MY_WAYBILLS, StateFilter(None))
async def handle_my_waybills(message: Message) -> None:
    """Placeholder for waybill history."""
    await message.answer(
        MSG_WAYBILLS_EMPTY,
        reply_markup=build_main_menu_keyboard(),
    )


@router.message(F.text == BTN_RECIPIENTS, StateFilter(None))
async def handle_recipients(message: Message) -> None:
    """Placeholder for recipients list."""
    await message.answer(
        MSG_RECIPIENTS_EMPTY,
        reply_markup=build_main_menu_keyboard(),
    )


@router.message(F.text == BTN_API_KEY, StateFilter(None))
async def handle_api_key_menu(
    message: Message,
    user_repository: UserRepository,
    state: FSMContext,
) -> None:
    """Show stored API key or ask the user to enter one."""
    if message.from_user is None:
        return

    user = await user_repository.get_user(message.from_user.id)

    if user is None or not user.api_key:
        await state.set_state(WaitingForApiKey.api_key)
        await message.answer(ASK_API_KEY_MESSAGE)
        return

    masked_key = mask_api_key(user.api_key, API_KEY_VISIBLE_CHARS)
    await message.answer(
        masked_key,
        reply_markup=build_replace_api_key_keyboard(),
    )


@router.message(F.text == BTN_SETTINGS, StateFilter(None))
async def handle_settings(message: Message) -> None:
    """Placeholder for bot settings."""
    await message.answer(
        MSG_SETTINGS_SOON,
        reply_markup=build_main_menu_keyboard(),
    )
