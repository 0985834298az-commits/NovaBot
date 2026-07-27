from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.constants import (
    CALLBACK_WAYBILL_EDIT_PRODUCTS,
    MSG_ORDER_ITEMS_UPDATED,
    MSG_TTN_ASK_PRODUCTS,
    MSG_TTN_INVALID_PRODUCTS,
    MSG_WAYBILLS_EMPTY,
    MSG_WAYBILLS_LIST_HEADER,
)
from app.handlers.states import WaybillWizard
from app.keyboards import build_main_menu_keyboard, build_waybill_actions_keyboard
from app.repositories.order_item_repository import OrderItemRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.order_service import format_waybill_details
from app.utils.order_items import parse_product_lines

router = Router(name="waybills")


def _parse_waybill_id(callback_data: str, prefix: str) -> int | None:
    if not callback_data.startswith(f"{prefix}:"):
        return None
    raw_id = callback_data[len(prefix) + 1 :]
    try:
        return int(raw_id)
    except ValueError:
        return None


async def show_active_waybills(
    message: Message,
    waybill_repository: WaybillRepository,
    order_item_repository: OrderItemRepository,
) -> None:
    """Render active waybills with dynamic numbering and order details."""
    if message.from_user is None:
        return

    waybills = await waybill_repository.get_active(message.from_user.id)
    if not waybills:
        await message.answer(
            MSG_WAYBILLS_EMPTY,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    await message.answer(MSG_WAYBILLS_LIST_HEADER)
    items_by_order = await order_item_repository.get_by_order_ids(
        [waybill.id for waybill in waybills],
    )

    for index, waybill in enumerate(waybills, start=1):
        items = items_by_order.get(waybill.id, [])
        await message.answer(
            format_waybill_details(index, waybill, items),
            reply_markup=build_waybill_actions_keyboard(waybill.id),
        )


@router.callback_query(F.data.startswith(f"{CALLBACK_WAYBILL_EDIT_PRODUCTS}:"))
async def handle_waybill_edit_products_start(
    callback: CallbackQuery,
    state: FSMContext,
    waybill_repository: WaybillRepository,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        return

    waybill_id = _parse_waybill_id(callback.data, CALLBACK_WAYBILL_EDIT_PRODUCTS)
    if waybill_id is None:
        await callback.answer("Некоректне замовлення", show_alert=True)
        return

    waybill = await waybill_repository.get_by_id(waybill_id, callback.from_user.id)
    if waybill is None or waybill.is_archived:
        await callback.answer()
        await callback.message.answer(
            MSG_WAYBILLS_EMPTY,
            reply_markup=build_main_menu_keyboard(),
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
        await message.answer(MSG_WAYBILLS_EMPTY, reply_markup=build_main_menu_keyboard())
        return

    waybill = await waybill_repository.get_by_id(int(waybill_id), message.from_user.id)
    if waybill is None or waybill.is_archived:
        await state.clear()
        await message.answer(MSG_WAYBILLS_EMPTY, reply_markup=build_main_menu_keyboard())
        return

    items = await order_item_repository.replace_items(int(waybill_id), product_names)
    await state.clear()
    await message.answer(MSG_ORDER_ITEMS_UPDATED)
    await show_active_waybills(
        message,
        waybill_repository,
        order_item_repository,
    )
