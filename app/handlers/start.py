from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.constants import ASK_API_KEY_MESSAGE, START_MESSAGE
from app.handlers.states import WaitingForApiKey
from app.keyboards import build_main_menu_keyboard
from app.nova_poshta import NovaPoshtaClient
from app.repositories.user_repository import UserRepository

router = Router(name="start")


@router.message(CommandStart())
async def handle_start(
    message: Message,
    user_repository: UserRepository,
    state: FSMContext,
) -> None:
    """Welcome authorized users and collect API key when missing."""
    if message.from_user is None:
        return

    user = await user_repository.get_or_create_user(message.from_user.id)

    if user.api_key:
        async with NovaPoshtaClient(user.api_key) as client:
            is_valid = await client.validate_api_key()

        if is_valid:
            await state.clear()
            await message.answer(
                START_MESSAGE,
                reply_markup=build_main_menu_keyboard(),
            )
            return

    await state.set_state(WaitingForApiKey.api_key)
    await message.answer(ASK_API_KEY_MESSAGE)
