from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from app.constants import (
    CALLBACK_WAYBILL_DELETE,
    CALLBACK_WAYBILL_DELETE_NO,
    CALLBACK_WAYBILL_DELETE_YES,
    CALLBACK_WAYBILL_EDIT_PRODUCTS,
    MSG_ACTION_CANCELLED,
    MSG_ORDER_ITEMS_UPDATED,
    MSG_TTN_ASK_PRODUCTS,
    MSG_TTN_INVALID_PRODUCTS,
    MSG_WAYBILL_DELETE_CONFIRM,
    MSG_WAYBILL_DELETE_FAILED,
    MSG_WAYBILL_DELETED,
)
from app.handlers.states import WaybillWizard
from app.keyboards import build_waybill_delete_keyboard
from app.nova_poshta.exceptions import NovaPoshtaError
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.order_item_repository import OrderItemRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.waybill_delete_service import delete_waybill_shipment
from app.services.waybill_list_service import render_my_waybills
from app.utils.order_items import parse_product_lines
from app.utils.waybill_status import is_list_active_status

router = Router(name="waybills")


def _parse_waybill_id(callback_data: str, prefix: str) -> int | None:
    if not callback_data.startswith(f"{prefix}:"):
        return None
    raw_id = callback_data[len(prefix) + 1 :]
    try:
        return int(raw_id)
    except ValueError:
        return None


@router.callback_query(F.data.startswith(f"{CALLBACK_WAYBILL_EDIT_PRODUCTS}:"))
async def handle_waybill_edit_products_start(
    callback: CallbackQuery,
    state: FSMContext,
    waybill_repository: WaybillRepository,
    order_item_repository: OrderItemRepository,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        return

    waybill_id = _parse_waybill_id(callback.data, CALLBACK_WAYBILL_EDIT_PRODUCTS)
    if waybill_id is None:
        await callback.answer("Некоректне замовлення", show_alert=True)
        return

    waybill = await waybill_repository.get_by_id(waybill_id, callback.from_user.id)
    if waybill is None or not is_list_active_status(waybill.shipment_status_code):
        await callback.answer()
        await render_my_waybills(
            callback.message,
            waybill_repository,
            order_item_repository,
            nova_poshta_account_repository,
            telegram_user_id=callback.from_user.id,
        )
        return

    await state.clear()
    await state.set_state(WaybillWizard.edit_products)
    await state.update_data(waybill_id=waybill_id)
    await callback.answer()
    await callback.message.answer(MSG_TTN_ASK_PRODUCTS)


@router.message(WaybillWizard.edit_products, F.text)
async def handle_waybill_edit_products_save(
    message: Message,
    state: FSMContext,
    waybill_repository: WaybillRepository,
    order_item_repository: OrderItemRepository,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
) -> None:
    if message.from_user is None or message.text is None:
        return

    product_names = parse_product_lines(message.text)
    if not product_names:
        await message.answer(MSG_TTN_INVALID_PRODUCTS)
        return

    data = await state.get_data()
    waybill_id = data.get("waybill_id")
    if waybill_id is None:
        await state.clear()
        await render_my_waybills(
            message,
            waybill_repository,
            order_item_repository,
            nova_poshta_account_repository,
        )
        return

    waybill = await waybill_repository.get_by_id(int(waybill_id), message.from_user.id)
    if waybill is None or not is_list_active_status(waybill.shipment_status_code):
        await state.clear()
        await render_my_waybills(
            message,
            waybill_repository,
            order_item_repository,
            nova_poshta_account_repository,
        )
        return

    await order_item_repository.replace_items(int(waybill_id), product_names)
    await state.clear()
    await message.answer(MSG_ORDER_ITEMS_UPDATED)
    await render_my_waybills(
        message,
        waybill_repository,
        order_item_repository,
        nova_poshta_account_repository,
    )


@router.callback_query(
    F.data.startswith(f"{CALLBACK_WAYBILL_DELETE}:")
    & ~F.data.startswith(f"{CALLBACK_WAYBILL_DELETE_YES}:")
    & ~F.data.startswith(f"{CALLBACK_WAYBILL_DELETE_NO}:"),
)
async def handle_waybill_delete_prompt(callback: CallbackQuery) -> None:
    if callback.data is None or callback.message is None:
        return

    waybill_id = _parse_waybill_id(callback.data, CALLBACK_WAYBILL_DELETE)
    if waybill_id is None:
        await callback.answer("Некоректне замовлення", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        MSG_WAYBILL_DELETE_CONFIRM,
        reply_markup=build_waybill_delete_keyboard(waybill_id),
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_WAYBILL_DELETE_YES}:"))
async def handle_waybill_delete_confirm(
    callback: CallbackQuery,
    waybill_repository: WaybillRepository,
    order_item_repository: OrderItemRepository,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        return

    waybill_id = _parse_waybill_id(callback.data, CALLBACK_WAYBILL_DELETE_YES)
    if waybill_id is None:
        await callback.answer("Некоректне замовлення", show_alert=True)
        return

    waybill = await waybill_repository.get_by_id(waybill_id, callback.from_user.id)
    if waybill is None or not is_list_active_status(waybill.shipment_status_code):
        await callback.answer()
        await render_my_waybills(
            callback.message,
            waybill_repository,
            order_item_repository,
            nova_poshta_account_repository,
            telegram_user_id=callback.from_user.id,
        )
        return

    try:
        await delete_waybill_shipment(
            waybill=waybill,
            telegram_user_id=callback.from_user.id,
            account_repository=nova_poshta_account_repository,
            waybill_repository=waybill_repository,
        )
    except NovaPoshtaError as exc:
        logger.error(
            "Waybill delete failed for user {} TTN {}: {}",
            callback.from_user.id,
            waybill.ttn_number,
            exc,
        )
        await callback.answer()
        await callback.message.answer(MSG_WAYBILL_DELETE_FAILED.format(error=str(exc)))
        return
    except Exception as exc:
        logger.exception(
            "Unexpected waybill delete failure for user {} TTN {}",
            callback.from_user.id,
            waybill.ttn_number,
        )
        await callback.answer()
        await callback.message.answer(MSG_WAYBILL_DELETE_FAILED.format(error=str(exc)))
        return

    await callback.answer()
    await callback.message.answer(MSG_WAYBILL_DELETED)
    await render_my_waybills(
        callback.message,
        waybill_repository,
        order_item_repository,
        nova_poshta_account_repository,
        telegram_user_id=callback.from_user.id,
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_WAYBILL_DELETE_NO}:"))
async def handle_waybill_delete_cancel(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await callback.message.answer(MSG_ACTION_CANCELLED)
