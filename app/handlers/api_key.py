from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from app.constants import (
    API_KEY_INVALID_MESSAGE,
    API_KEY_SAVED_MESSAGE,
    ASK_API_KEY_MESSAGE,
    CALLBACK_REPLACE_API_KEY,
)
from app.handlers.states import WaitingForApiKey
from app.keyboards import build_main_menu_keyboard
from app.nova_poshta import NovaPoshtaClient
from app.repositories.user_repository import UserRepository

router = Router(name="api_key")


@router.callback_query(F.data == CALLBACK_REPLACE_API_KEY)
async def handle_replace_api_key(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Start replacing the stored Nova Poshta API key."""
    await state.set_state(WaitingForApiKey.api_key)
    await callback.answer()

    if callback.message is not None:
        await callback.message.answer(ASK_API_KEY_MESSAGE)


@router.message(WaitingForApiKey.api_key, F.text)
async def handle_api_key_input(
    message: Message,
    user_repository: UserRepository,
    state: FSMContext,
) -> None:
    """Validate and store the Nova Poshta API key."""
    if message.from_user is None or message.text is None:
        return

    api_key = message.text.strip()
    if not api_key:
        await message.answer(API_KEY_INVALID_MESSAGE)
        return

    logger.info("Validating Nova Poshta API key for user {}", message.from_user.id)

    async with NovaPoshtaClient(api_key) as client:
        is_valid = await client.validate_api_key()

    if not is_valid:
        await message.answer(API_KEY_INVALID_MESSAGE)
        return

    await user_repository.save_api_key(message.from_user.id, api_key)
    await state.clear()
    await message.answer(
        API_KEY_SAVED_MESSAGE,
        reply_markup=build_main_menu_keyboard(),
    )


@router.message(WaitingForApiKey.api_key)
async def handle_api_key_invalid_input(message: Message) -> None:
    """Reject non-text input while waiting for an API key."""
    await message.answer(API_KEY_INVALID_MESSAGE)
