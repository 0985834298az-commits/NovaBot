from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.constants import MSG_NP_ASK_ACCOUNT_NAME, START_MESSAGE
from app.handlers.states import NovaPoshtaAccountWizard
from app.keyboards import build_main_menu_keyboard
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.user_repository import UserRepository

router = Router(name="start")


@router.message(CommandStart())
async def handle_start(
    message: Message,
    user_repository: UserRepository,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    state: FSMContext,
) -> None:
    """Welcome authorized users and collect a Nova Poshta account when missing."""
    if message.from_user is None:
        return

    await user_repository.get_or_create_user(message.from_user.id)

    active_account = await nova_poshta_account_repository.get_active_account(
        message.from_user.id,
    )
    if active_account is not None:
        await state.clear()
        await message.answer(
            START_MESSAGE,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    await state.set_state(NovaPoshtaAccountWizard.add_name)
    await message.answer(MSG_NP_ASK_ACCOUNT_NAME)
