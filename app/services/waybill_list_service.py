"""Single source of truth for rendering the My Waybills screen."""

from __future__ import annotations

from aiogram.types import Message
from loguru import logger

from app.constants import MSG_WAYBILLS_EMPTY, MSG_WAYBILLS_FOOTER, MSG_WAYBILLS_LIST_HEADER
from app.keyboards import build_waybill_actions_keyboard
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.order_item_repository import OrderItemRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.order_service import format_waybill_details
from app.services.waybill_sync_service import sync_user_waybills


async def _run_sync(
    *,
    telegram_user_id: int,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
) -> None:
    """Synchronize waybills silently before rendering."""
    try:
        await sync_user_waybills(
            telegram_user_id=telegram_user_id,
            account_repository=nova_poshta_account_repository,
            waybill_repository=waybill_repository,
        )
    except Exception as exc:
        logger.exception(
            "Automatic waybill sync failed for user {}: {}",
            telegram_user_id,
            exc,
        )


def _log_waybill_render_state(
    *,
    telegram_user_id: int,
    all_shipments: list,
    active_shipments: list,
) -> None:
    """Log shipment counts and per-row fields before rendering My Waybills."""
    statuses = [waybill.shipment_status_code for waybill in all_shipments]
    deleted_flags = [waybill.is_deleted for waybill in all_shipments]
    logger.info(
        "My Waybills render for user {}: total_in_db={} active={} statuses={} deleted_flags={}",
        telegram_user_id,
        len(all_shipments),
        len(active_shipments),
        statuses,
        deleted_flags,
    )
    for waybill in all_shipments:
        logger.info(
            "My Waybills shipment: id={} ttn={} status={} is_deleted={} is_archived={}",
            waybill.id,
            waybill.ttn_number,
            waybill.shipment_status_code,
            waybill.is_deleted,
            waybill.is_archived,
        )


async def render_my_waybills(
    message: Message,
    waybill_repository: WaybillRepository,
    order_item_repository: OrderItemRepository,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    *,
    telegram_user_id: int | None = None,
) -> None:
    """Render the My Waybills screen. This is the only waybill list renderer."""
    user_id = telegram_user_id
    if user_id is None:
        if message.from_user is None:
            return
        user_id = message.from_user.id

    await _run_sync(
        telegram_user_id=user_id,
        nova_poshta_account_repository=nova_poshta_account_repository,
        waybill_repository=waybill_repository,
    )

    all_shipments = await waybill_repository.get_all_for_user(user_id)
    active_shipments = await waybill_repository.get_active_shipments(user_id)
    _log_waybill_render_state(
        telegram_user_id=user_id,
        all_shipments=all_shipments,
        active_shipments=active_shipments,
    )

    if not active_shipments:
        await message.answer(MSG_WAYBILLS_EMPTY)
        return

    await message.answer(MSG_WAYBILLS_LIST_HEADER)
    items_by_order = await order_item_repository.get_by_order_ids(
        [waybill.id for waybill in active_shipments],
    )

    for index, waybill in enumerate(active_shipments, start=1):
        items = items_by_order.get(waybill.id, [])
        await message.answer(
            format_waybill_details(index, waybill, items),
            reply_markup=build_waybill_actions_keyboard(waybill.id),
        )

    await message.answer(MSG_WAYBILLS_FOOTER)
