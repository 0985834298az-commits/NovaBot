from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.constants import (
    CALLBACK_ACCOUNT_SEL_CANCEL,
    CALLBACK_ACCOUNT_SEL_CREATE_ANYWAY,
    CALLBACK_ACCOUNT_SEL_PICK,
    CALLBACK_ACCOUNT_SEL_SELECT,
    MSG_TTN_CANCELLED,
)
from app.keyboards import build_main_menu_keyboard
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.order_item_repository import OrderItemRepository
from app.repositories.payment_card_repository import PaymentCardRepository
from app.repositories.recipient_repository import RecipientRepository
from app.repositories.user_repository import UserRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.ttn_creation_flow import (
    clear_pending_ttn,
    execute_pending_ttn_creation,
    show_manual_account_selection,
)

router = Router(name="account_selection")


def _parse_account_id(callback_data: str, prefix: str) -> int | None:
    if not callback_data.startswith(f"{prefix}:"):
        return None
    raw_id = callback_data[len(prefix) + 1 :]
    try:
        return int(raw_id)
    except ValueError:
        return None


@router.callback_query(F.data == CALLBACK_ACCOUNT_SEL_CREATE_ANYWAY)
async def handle_account_sel_create_anyway(
    callback: CallbackQuery,
    state: FSMContext,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    recipient_repository: RecipientRepository,
    payment_card_repository: PaymentCardRepository,
    waybill_repository: WaybillRepository,
    order_item_repository: OrderItemRepository,
    user_repository: UserRepository,
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    await callback.answer()
    await execute_pending_ttn_creation(
        callback.message,
        state,
        nova_poshta_account_repository=nova_poshta_account_repository,
        recipient_repository=recipient_repository,
        payment_card_repository=payment_card_repository,
        waybill_repository=waybill_repository,
        order_item_repository=order_item_repository,
        user_repository=user_repository,
        force_current=True,
    )


@router.callback_query(F.data == CALLBACK_ACCOUNT_SEL_SELECT)
async def handle_account_sel_select(
    callback: CallbackQuery,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    await callback.answer()
    await show_manual_account_selection(
        callback.message,
        nova_poshta_account_repository,
        waybill_repository,
        callback.from_user.id,
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_ACCOUNT_SEL_PICK}:"))
async def handle_account_sel_pick(
    callback: CallbackQuery,
    state: FSMContext,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    recipient_repository: RecipientRepository,
    payment_card_repository: PaymentCardRepository,
    waybill_repository: WaybillRepository,
    order_item_repository: OrderItemRepository,
    user_repository: UserRepository,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        return

    account_id = _parse_account_id(callback.data, CALLBACK_ACCOUNT_SEL_PICK)
    if account_id is None:
        await callback.answer("Некоректний акаунт", show_alert=True)
        return

    await callback.answer()
    await execute_pending_ttn_creation(
        callback.message,
        state,
        nova_poshta_account_repository=nova_poshta_account_repository,
        recipient_repository=recipient_repository,
        payment_card_repository=payment_card_repository,
        waybill_repository=waybill_repository,
        order_item_repository=order_item_repository,
        user_repository=user_repository,
        account_id=account_id,
    )


@router.callback_query(F.data == CALLBACK_ACCOUNT_SEL_CANCEL)
async def handle_account_sel_cancel(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.message is None:
        return

    await callback.answer()
    await clear_pending_ttn(state)
    await state.clear()
    await callback.message.answer(
        MSG_TTN_CANCELLED,
        reply_markup=build_main_menu_keyboard(),
    )
