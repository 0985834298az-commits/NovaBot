from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.constants import CALLBACK_REPLACE_API_KEY, MSG_NP_ASK_ACCOUNT_NAME
from app.handlers.states import NovaPoshtaAccountWizard

router = Router(name="api_key")


@router.callback_query(F.data == CALLBACK_REPLACE_API_KEY)
async def handle_replace_api_key(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Start adding a Nova Poshta account."""
    await state.clear()
    await state.set_state(NovaPoshtaAccountWizard.add_name)
    await callback.answer()

    if callback.message is not None:
        await callback.message.answer(MSG_NP_ASK_ACCOUNT_NAME)
