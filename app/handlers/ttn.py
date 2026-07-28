from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.constants import (
    MSG_NO_ACTIVE_NP_ACCOUNT,
    MSG_NO_ACTIVE_PAYMENT_CARD,
    MSG_TTN_ASK_ORDER,
    MSG_TTN_ASK_PRODUCTS,
    MSG_TTN_INVALID_ORDER_FORMAT,
    MSG_TTN_INVALID_PRODUCTS,
    MSG_TTN_SENDER_NOT_CONFIGURED,
)
from app.handlers.states import TtnWizard
from app.keyboards import build_main_menu_keyboard
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.order_item_repository import OrderItemRepository
from app.repositories.payment_card_repository import PaymentCardRepository
from app.repositories.recipient_repository import RecipientRepository
from app.repositories.user_repository import UserRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.nova_poshta_account_service import ensure_active_account_sender_cache
from app.services.payment_card_service import is_active_card_ready
from app.services.sender_cache import get_sender_cache_error
from app.services.ttn_creation_flow import (
    process_ttn_account_selection,
    resolve_ttn_payment_card,
)
from app.services.ttn_service import parse_ttn_order_message
from app.utils.order_items import parse_product_lines

router = Router(name="ttn")


def _sender_not_configured_message(telegram_user_id: int) -> str:
    error = (
        get_sender_cache_error(telegram_user_id)
        or "Sender location is not configured"
    )
    return MSG_TTN_SENDER_NOT_CONFIGURED.format(error=error)


async def begin_ttn_wizard(
    message: Message,
    state: FSMContext,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    payment_card_repository: PaymentCardRepository,
) -> None:
    """Start single-message TTN creation."""
    if message.from_user is None:
        return

    active_account = await nova_poshta_account_repository.get_active_account(message.from_user.id)
    if active_account is None:
        await message.answer(
            MSG_NO_ACTIVE_NP_ACCOUNT,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    active_card, _ = await resolve_ttn_payment_card(
        telegram_user_id=message.from_user.id,
        nova_poshta_account_repository=nova_poshta_account_repository,
        payment_card_repository=payment_card_repository,
        stage="begin_wizard",
    )
    if not is_active_card_ready(active_card):
        await message.answer(
            MSG_NO_ACTIVE_PAYMENT_CARD,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    try:
        prepared = await ensure_active_account_sender_cache(
            nova_poshta_account_repository,
            message.from_user.id,
        )
    except RuntimeError:
        await message.answer(
            _sender_not_configured_message(message.from_user.id),
            reply_markup=build_main_menu_keyboard(),
        )
        return

    if prepared is None:
        await message.answer(
            MSG_NO_ACTIVE_NP_ACCOUNT,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    await state.clear()
    await state.set_state(TtnWizard.order_input)
    await message.answer(MSG_TTN_ASK_ORDER)


@router.message(TtnWizard.order_input, F.text)
async def handle_ttn_order_input(
    message: Message,
    state: FSMContext,
) -> None:
    """Parse recipient data and ask for ordered products."""
    if message.text is None:
        return

    order = parse_ttn_order_message(message.text)
    if order is None:
        await message.answer(MSG_TTN_INVALID_ORDER_FORMAT)
        return

    await state.update_data(
        recipient_name=order.recipient_name,
        recipient_phone=order.recipient_phone,
        city_query=order.city_query,
        warehouse_number=order.warehouse_number,
        cod_amount=order.cod_amount,
    )
    await state.set_state(TtnWizard.products_input)
    await message.answer(MSG_TTN_ASK_PRODUCTS)


@router.message(TtnWizard.products_input, F.text)
async def handle_ttn_products_input(
    message: Message,
    state: FSMContext,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    recipient_repository: RecipientRepository,
    payment_card_repository: PaymentCardRepository,
    waybill_repository: WaybillRepository,
    order_item_repository: OrderItemRepository,
    user_repository: UserRepository,
) -> None:
    """Create a TTN after products are received."""
    if message.from_user is None or message.text is None:
        return

    product_names = parse_product_lines(message.text)
    if not product_names:
        await message.answer(MSG_TTN_INVALID_PRODUCTS)
        return

    data = await state.get_data()
    await process_ttn_account_selection(
        message,
        state,
        source="ttn",
        product_names=product_names,
        cod_amount=str(data.get("cod_amount") or "0"),
        nova_poshta_account_repository=nova_poshta_account_repository,
        waybill_repository=waybill_repository,
        user_repository=user_repository,
        recipient_repository=recipient_repository,
        payment_card_repository=payment_card_repository,
        order_item_repository=order_item_repository,
        recipient_name=str(data.get("recipient_name") or ""),
        recipient_phone=str(data.get("recipient_phone") or ""),
        city_query=str(data.get("city_query") or ""),
        warehouse_number=str(data.get("warehouse_number") or ""),
    )
