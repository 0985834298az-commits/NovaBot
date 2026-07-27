from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger

from app.constants import (
    MSG_NO_ACTIVE_NP_ACCOUNT,
    MSG_NO_ACTIVE_PAYMENT_CARD,
    MSG_TTN_ASK_ORDER,
    MSG_TTN_ASK_PRODUCTS,
    MSG_TTN_CREATE_FAILED,
    MSG_TTN_CREATING,
    MSG_TTN_INVALID_ORDER_FORMAT,
    MSG_TTN_INVALID_PRODUCTS,
    MSG_TTN_PRINT_LINK,
    MSG_TTN_SENDER_NOT_CONFIGURED,
)
from app.handlers.states import TtnWizard
from app.keyboards import build_main_menu_keyboard
from app.nova_poshta import NovaPoshtaClient
from app.nova_poshta.exceptions import NovaPoshtaError
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.order_item_repository import OrderItemRepository
from app.repositories.payment_card_repository import PaymentCardRepository
from app.repositories.recipient_repository import RecipientRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.nova_poshta_account_service import ensure_active_account_sender_cache
from app.services.order_service import create_ttn_with_order_items
from app.services.sender_cache import get_sender_cache_error
from app.services.ttn_service import (
    TtnOrderInput,
    build_print_link,
    format_ttn_success_message,
    parse_ttn_order_message,
    prepare_wizard_data_from_order,
)
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

    active_card = await payment_card_repository.get_active_card(message.from_user.id)
    if active_card is None:
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
    except RuntimeError as exc:
        await message.answer(
            _sender_not_configured_message(message.from_user.id),
            reply_markup=build_main_menu_keyboard(),
        )
        logger.error(
            "TTN wizard blocked for user {}: {}",
            message.from_user.id,
            exc,
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
) -> None:
    """Create a TTN after products are received."""
    if message.from_user is None or message.text is None:
        return

    product_names = parse_product_lines(message.text)
    if not product_names:
        await message.answer(MSG_TTN_INVALID_PRODUCTS)
        return

    active_card = await payment_card_repository.get_active_card(message.from_user.id)
    if active_card is None:
        await state.clear()
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
    except RuntimeError as exc:
        await state.clear()
        await message.answer(
            _sender_not_configured_message(message.from_user.id),
            reply_markup=build_main_menu_keyboard(),
        )
        logger.error(
            "TTN creation blocked for user {}: {}",
            message.from_user.id,
            exc,
        )
        return

    if prepared is None:
        await state.clear()
        await message.answer(
            MSG_NO_ACTIVE_NP_ACCOUNT,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    api_key, sender_location = prepared

    data = await state.get_data()
    order = TtnOrderInput(
        recipient_name=str(data.get("recipient_name") or ""),
        recipient_phone=str(data.get("recipient_phone") or ""),
        city_query=str(data.get("city_query") or ""),
        warehouse_number=str(data.get("warehouse_number") or ""),
        cod_amount=str(data.get("cod_amount") or ""),
    )

    await message.answer(MSG_TTN_CREATING)

    try:
        async with NovaPoshtaClient(api_key) as client:
            wizard_data, sender_profile = await prepare_wizard_data_from_order(
                client,
                order,
                sender_location,
            )
        wizard_data["payment_card_number"] = active_card.card_number
        document, _waybill = await create_ttn_with_order_items(
            telegram_user_id=message.from_user.id,
            wizard_data=wizard_data,
            sender_profile=sender_profile,
            product_names=product_names,
            api_key=api_key,
            recipient_repository=recipient_repository,
            waybill_repository=waybill_repository,
            order_item_repository=order_item_repository,
            save_recipient=True,
        )
    except NovaPoshtaError as exc:
        logger.error("TTN creation failed for user {}: {}", message.from_user.id, exc)
        await message.answer(MSG_TTN_CREATE_FAILED.format(error=str(exc)))
        return

    ttn_number = str(document.get("IntDocNumber") or "—")
    reference = str(document.get("Ref") or "")
    delivery_cost = document.get("CostOnSite") or document.get("DocumentCost")

    await state.clear()
    await message.answer(
        format_ttn_success_message(
            ttn_number=ttn_number,
            delivery_cost=delivery_cost,
        ),
        reply_markup=build_main_menu_keyboard(),
    )

    if reference:
        print_link = build_print_link(reference, api_key)
        await message.answer(MSG_TTN_PRINT_LINK.format(link=print_link))
