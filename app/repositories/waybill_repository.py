from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import WAYBILL_INITIAL_STATUS, WAYBILL_INITIAL_STATUS_CODE
from app.models.waybill import Waybill


class WaybillRepository:
    """Persistence layer for TTN waybills."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_waybill(
        self,
        *,
        telegram_user_id: int,
        ttn_number: str,
        document_ref: str,
        recipient_name: str,
        recipient_phone: str,
        city_name: str,
        city_ref: str,
        warehouse_number: str,
        warehouse_ref: str,
        cod_amount: str,
        delivery_cost: str | None,
        cargo_description: str,
        weight: str,
        declared_cost: str,
        shipment_status: str = WAYBILL_INITIAL_STATUS,
        shipment_status_code: str = WAYBILL_INITIAL_STATUS_CODE,
    ) -> Waybill:
        """Persist a newly created TTN."""
        waybill = Waybill(
            telegram_user_id=telegram_user_id,
            ttn_number=ttn_number.strip(),
            document_ref=document_ref.strip(),
            recipient_name=recipient_name.strip(),
            recipient_phone=recipient_phone.strip(),
            city_name=city_name.strip(),
            city_ref=city_ref.strip(),
            warehouse_number=warehouse_number.strip().lstrip("№"),
            warehouse_ref=warehouse_ref.strip(),
            cod_amount=cod_amount.strip(),
            delivery_cost=delivery_cost.strip() if delivery_cost else None,
            cargo_description=cargo_description.strip(),
            weight=weight.strip(),
            declared_cost=declared_cost.strip(),
            shipment_status=shipment_status.strip(),
            shipment_status_code=shipment_status_code.strip(),
            is_archived=False,
        )
        self._session.add(waybill)
        await self._session.flush()
        await self._session.refresh(waybill)
        return waybill

    async def get_active(self, telegram_user_id: int) -> list[Waybill]:
        """Return active (not archived) waybills ordered by creation time."""
        result = await self._session.execute(
            select(Waybill)
            .where(
                Waybill.telegram_user_id == telegram_user_id,
                Waybill.is_archived.is_(False),
            )
            .order_by(Waybill.created_at.asc(), Waybill.id.asc()),
        )
        return list(result.scalars().all())

    async def get_all_active(self) -> list[Waybill]:
        """Return all active waybills across users."""
        result = await self._session.execute(
            select(Waybill)
            .where(Waybill.is_archived.is_(False))
            .order_by(Waybill.telegram_user_id.asc(), Waybill.created_at.asc()),
        )
        return list(result.scalars().all())

    async def update_tracking_status(
        self,
        waybill: Waybill,
        *,
        shipment_status: str,
        shipment_status_code: str,
        last_checked_at: datetime,
    ) -> Waybill:
        """Update shipment status from tracking API."""
        waybill.shipment_status = shipment_status.strip()
        waybill.shipment_status_code = shipment_status_code.strip()
        waybill.last_checked_at = last_checked_at
        await self._session.flush()
        await self._session.refresh(waybill)
        return waybill

    async def archive_waybill(
        self,
        waybill: Waybill,
        *,
        shipment_status: str,
        shipment_status_code: str,
        archived_at: datetime,
        last_checked_at: datetime,
    ) -> Waybill:
        """Move a waybill to the archive."""
        waybill.shipment_status = shipment_status.strip()
        waybill.shipment_status_code = shipment_status_code.strip()
        waybill.is_archived = True
        waybill.archived_at = archived_at
        waybill.last_checked_at = last_checked_at
        await self._session.flush()
        await self._session.refresh(waybill)
        return waybill
