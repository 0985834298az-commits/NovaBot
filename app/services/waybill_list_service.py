"""Single source of truth for rendering the My Waybills screen."""

from __future__ import annotations

from aiogram.types import Message
from loguru import logger

from app.constants import MSG_WAYBILLS_EMPTY, MSG_WAYBILLS_FOOTER, MSG_WAYBILLS_LIST_HEADER
from app.keyboards import build_waybill_actions_keyboard, build_waybills_footer_keyboard
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.order_item_repository import OrderItemRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.order_service import format_waybill_details
from app.services.waybill_sync_service import sync_user_waybills
from app.utils.waybill_status import filter_list_active_waybills


async def _run_sync(
    *,
    telegram_user_id: int,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
) -> bool:
    """Synchronize waybills silently and return False when the active account failed."""
    active_account = await nova_poshta_account_repository.get_active_account(telegram_user_id)
    if active_account is None:
        return True

    result = await sync_user_waybills(
        telegram_user_id=telegram_user_id,
        account_repository=nova_poshta_account_repository,
        waybill_repository=waybill_repository,
    )
    return active_account.account_name not in result.failed_accounts


async def render_my_waybills(
    message: Message,
    waybill_repository: WaybillRepository,
    order_item_repository: OrderItemRepository,
    *,
    nova_poshta_account_repository: NovaPoshtaAccountRepository | None = None,
    sync_before_show: bool = False,
) -> None:
    """Render the My Waybills screen. This is the only waybill list renderer."""
    if message.from_user is None:
        return

    if sync_before_show and nova_poshta_account_repository is not None:
        try:
            await _run_sync(
                telegram_user_id=message.from_user.id,
                nova_poshta_account_repository=nova_poshta_account_repository,
                waybill_repository=waybill_repository,
            )
        except Exception as exc:
            logger.exception(
                "Automatic waybill sync failed for user {}: {}",
                message.from_user.id,
                exc,
            )

    shipments = await waybill_repository.get_all_for_user(message.from_user.id)
    active_shipments = filter_list_active_waybills(shipments)

    if not active_shipments:
        await message.answer(
            MSG_WAYBILLS_EMPTY,
            reply_markup=build_waybills_footer_keyboard(),
        )
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

    await message.answer(
        MSG_WAYBILLS_FOOTER,
        reply_markup=build_waybills_footer_keyboard(),
    )
