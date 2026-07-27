from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger

from app.constants import MSG_NP_ASK_ACCOUNT_NAME, START_MESSAGE
from app.handlers.states import NovaPoshtaAccountWizard
from app.keyboards import build_main_menu_keyboard
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.order_item_repository import OrderItemRepository
from app.repositories.user_repository import UserRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.waybill_sync_service import sync_user_waybills

router = Router(name="start")


@router.message(CommandStart())
async def handle_start(
    message: Message,
    user_repository: UserRepository,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
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
        try:
            await sync_user_waybills(
                telegram_user_id=message.from_user.id,
                account_repository=nova_poshta_account_repository,
                waybill_repository=waybill_repository,
            )
        except Exception as exc:
            logger.exception(
                "Automatic waybill sync failed on /start for user {}: {}",
                message.from_user.id,
                exc,
            )
        await state.clear()
        await message.answer(
            START_MESSAGE,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    await state.set_state(NovaPoshtaAccountWizard.add_name)
    await message.answer(MSG_NP_ASK_ACCOUNT_NAME)
