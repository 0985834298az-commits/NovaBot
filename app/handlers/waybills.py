from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from app.constants import (
    CALLBACK_WAYBILL_EDIT_PRODUCTS,
    CALLBACK_WAYBILL_SYNC,
    MSG_ORDER_ITEMS_UPDATED,
    MSG_SYNC_COMPLETE,
    MSG_SYNC_FAILED,
    MSG_SYNC_IN_PROGRESS,
    MSG_TTN_ASK_PRODUCTS,
    MSG_TTN_INVALID_PRODUCTS,
)
from app.handlers.states import WaybillWizard
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.order_item_repository import OrderItemRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.waybill_list_service import render_my_waybills
from app.services.waybill_sync_service import sync_user_waybills
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


@router.callback_query(F.data == CALLBACK_WAYBILL_SYNC)
async def handle_waybill_sync(
    callback: CallbackQuery,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
    order_item_repository: OrderItemRepository,
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    await callback.answer()
    progress_message = await callback.message.answer(MSG_SYNC_IN_PROGRESS)
    try:
        result = await sync_user_waybills(
            telegram_user_id=callback.from_user.id,
            account_repository=nova_poshta_account_repository,
            waybill_repository=waybill_repository,
        )
    except Exception as exc:
        logger.exception("Manual waybill sync failed for user {}: {}", callback.from_user.id, exc)
        await progress_message.edit_text(MSG_SYNC_FAILED)
        return

    active_account = await nova_poshta_account_repository.get_active_account(
        callback.from_user.id,
    )
    if active_account and active_account.account_name in result.failed_accounts:
        logger.error(
            "Manual waybill sync failed for user {}: active account {} failed",
            callback.from_user.id,
            active_account.account_name,
        )
        await progress_message.edit_text(MSG_SYNC_FAILED)
        return

    await progress_message.edit_text(
        MSG_SYNC_COMPLETE.format(
            added=result.added,
            updated=result.updated,
            deleted=result.deleted,
        ),
    )
    await render_my_waybills(
        callback.message,
        waybill_repository,
        order_item_repository,
        telegram_user_id=callback.from_user.id,
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_WAYBILL_EDIT_PRODUCTS}:"))
async def handle_waybill_edit_products_start(
    callback: CallbackQuery,
    state: FSMContext,
    waybill_repository: WaybillRepository,
    order_item_repository: OrderItemRepository,
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
        )
        return

    waybill = await waybill_repository.get_by_id(int(waybill_id), message.from_user.id)
    if waybill is None or not is_list_active_status(waybill.shipment_status_code):
        await state.clear()
        await render_my_waybills(
            message,
            waybill_repository,
            order_item_repository,
        )
        return

    await order_item_repository.replace_items(int(waybill_id), product_names)
    await state.clear()
    await message.answer(MSG_ORDER_ITEMS_UPDATED)
    await render_my_waybills(
        message,
        waybill_repository,
        order_item_repository,
    )
