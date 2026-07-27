from __future__ import annotations

import asyncio

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.constants import WAYBILL_CHECK_INTERVAL_SECONDS
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.waybill_sync_service import sync_all_users_waybills


async def run_background_waybill_sync(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Synchronize all user shipments on a fixed interval."""
    while True:
        try:
            async with session_factory() as session:
                await sync_all_users_waybills(
                    account_repository=NovaPoshtaAccountRepository(session),
                    waybill_repository=WaybillRepository(session),
                )
                await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Background waybill sync failed: {}", exc)

        await asyncio.sleep(WAYBILL_CHECK_INTERVAL_SECONDS)
