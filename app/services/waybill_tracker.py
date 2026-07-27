from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.constants import WAYBILL_CHECK_INTERVAL_SECONDS
from app.nova_poshta import NovaPoshtaClient
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.nova_poshta_account_service import get_active_api_key
from app.utils.waybill_status import format_status_label, parse_status_documents

TRACKING_BATCH_SIZE = 100


def _chunk_waybills(waybills: list, size: int) -> list[list]:
    return [waybills[index : index + size] for index in range(0, len(waybills), size)]


async def check_active_waybill_statuses(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Poll Nova Poshta and archive waybills that left the Created state."""
    async with session_factory() as session:
        waybill_repository = WaybillRepository(session)
        account_repository = NovaPoshtaAccountRepository(session)
        active_waybills = await waybill_repository.get_all_active_shipments()
        if not active_waybills:
            return

        waybills_by_user: dict[int, list] = defaultdict(list)
        for waybill in active_waybills:
            waybills_by_user[waybill.telegram_user_id].append(waybill)

        checked_at = datetime.now(UTC)

        for telegram_user_id, user_waybills in waybills_by_user.items():
            api_key = await get_active_api_key(account_repository, telegram_user_id)
            if api_key is None:
                logger.warning(
                    "Skipping waybill status check for user {}: active NP account missing",
                    telegram_user_id,
                )
                continue

            async with NovaPoshtaClient(api_key) as client:
                for batch in _chunk_waybills(user_waybills, TRACKING_BATCH_SIZE):
                    documents = [
                        {
                            "DocumentNumber": waybill.ttn_number,
                            "Phone": waybill.recipient_phone,
                        }
                        for waybill in batch
                    ]
                    response = await client.get_status_documents(documents)
                    statuses = parse_status_documents(response)
                    status_by_number = {
                        status["number"]: status for status in statuses
                    }

                    for waybill in batch:
                        tracking = status_by_number.get(waybill.ttn_number)
                        if tracking is None:
                            waybill.last_checked_at = checked_at
                            continue

                        shipment_status_code = tracking["status_code"]
                        shipment_status = format_status_label(
                            shipment_status_code,
                            tracking["status"],
                        )

                        await waybill_repository.update_tracking_status(
                            waybill,
                            shipment_status=shipment_status,
                            shipment_status_code=shipment_status_code,
                            last_checked_at=checked_at,
                        )
                        logger.info(
                            "Updated waybill {} for user {} with status {}",
                            waybill.ttn_number,
                            telegram_user_id,
                            shipment_status,
                        )

        await session.commit()


async def run_waybill_status_checker(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Periodically check active waybill statuses."""
    while True:
        try:
            await check_active_waybill_statuses(session_factory)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Waybill status checker failed: {}", exc)

        await asyncio.sleep(WAYBILL_CHECK_INTERVAL_SECONDS)
