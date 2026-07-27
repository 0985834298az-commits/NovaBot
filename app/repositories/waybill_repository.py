from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    WAYBILL_DELETED_STATUS_CODES,
    WAYBILL_INITIAL_STATUS,
    WAYBILL_INITIAL_STATUS_CODE,
    WAYBILL_LIST_ACTIVE_STATUS_CODES,
)
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
        nova_poshta_account_id: int | None = None,
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
            nova_poshta_account_id=nova_poshta_account_id,
            shipment_status=shipment_status.strip(),
            shipment_status_code=shipment_status_code.strip(),
            is_archived=False,
        )
        self._session.add(waybill)
        await self._session.flush()
        await self._session.refresh(waybill)
        return waybill

    async def get_active(self, telegram_user_id: int) -> list[Waybill]:
        """Return in-progress waybills shown in the My Waybills list."""
        result = await self._session.execute(
            select(Waybill)
            .where(
                Waybill.telegram_user_id == telegram_user_id,
                Waybill.shipment_status_code.in_(WAYBILL_LIST_ACTIVE_STATUS_CODES),
            )
            .order_by(Waybill.created_at.asc(), Waybill.id.asc()),
        )
        return list(result.scalars().all())

    async def get_all_active(self) -> list[Waybill]:
        """Return all visible waybills across users."""
        result = await self._session.execute(
            select(Waybill).order_by(Waybill.telegram_user_id.asc(), Waybill.created_at.asc()),
        )
        return list(result.scalars().all())

    async def get_by_account_id(
        self,
        telegram_user_id: int,
        nova_poshta_account_id: int,
    ) -> list[Waybill]:
        """Return all waybills linked to a Nova Poshta account."""
        result = await self._session.execute(
            select(Waybill).where(
                Waybill.telegram_user_id == telegram_user_id,
                Waybill.nova_poshta_account_id == nova_poshta_account_id,
            ),
        )
        return list(result.scalars().all())

    async def get_unassigned(self, telegram_user_id: int) -> list[Waybill]:
        """Return waybills that are not linked to a Nova Poshta account yet."""
        result = await self._session.execute(
            select(Waybill).where(
                Waybill.telegram_user_id == telegram_user_id,
                Waybill.nova_poshta_account_id.is_(None),
            ),
        )
        return list(result.scalars().all())

    async def get_current_month_cod_total(self, nova_poshta_account_id: int) -> Decimal:
        """Return total COD for an account in the current month, excluding deleted TTNs."""
        now = datetime.now().astimezone()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        result = await self._session.execute(
            select(Waybill.cod_amount, Waybill.shipment_status_code).where(
                Waybill.nova_poshta_account_id == nova_poshta_account_id,
                Waybill.created_at >= month_start,
                Waybill.shipment_status_code.notin_(WAYBILL_DELETED_STATUS_CODES),
            ),
        )
        total = Decimal(0)
        for raw_amount, _status_code in result.all():
            if raw_amount is None or not str(raw_amount).strip():
                continue
            normalized = str(raw_amount).strip().replace(",", ".")
            try:
                total += Decimal(normalized)
            except Exception:
                continue
        return total

    async def get_by_id(
        self,
        waybill_id: int,
        telegram_user_id: int,
    ) -> Waybill | None:
        """Return a waybill owned by the Telegram user."""
        result = await self._session.execute(
            select(Waybill).where(
                Waybill.id == waybill_id,
                Waybill.telegram_user_id == telegram_user_id,
            ),
        )
        return result.scalar_one_or_none()

    async def get_by_ttn_number(
        self,
        telegram_user_id: int,
        ttn_number: str,
    ) -> Waybill | None:
        """Return a waybill by TTN number."""
        result = await self._session.execute(
            select(Waybill).where(
                Waybill.telegram_user_id == telegram_user_id,
                Waybill.ttn_number == ttn_number.strip(),
            ),
        )
        return result.scalar_one_or_none()

    async def update_from_sync(
        self,
        waybill: Waybill,
        *,
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
        shipment_status: str,
        shipment_status_code: str,
        nova_poshta_account_id: int | None = None,
        synced_at: datetime,
    ) -> Waybill:
        """Update waybill fields from Nova Poshta synchronization."""
        waybill.ttn_number = ttn_number.strip()
        waybill.document_ref = document_ref.strip()
        waybill.recipient_name = recipient_name.strip()
        waybill.recipient_phone = recipient_phone.strip()
        waybill.city_name = city_name.strip()
        waybill.city_ref = city_ref.strip()
        waybill.warehouse_number = warehouse_number.strip().lstrip("№")
        waybill.warehouse_ref = warehouse_ref.strip()
        waybill.cod_amount = cod_amount.strip()
        waybill.delivery_cost = delivery_cost.strip() if delivery_cost else None
        waybill.cargo_description = cargo_description.strip()
        waybill.weight = weight.strip()
        waybill.declared_cost = declared_cost.strip()
        waybill.shipment_status = shipment_status.strip()
        waybill.shipment_status_code = shipment_status_code.strip()
        waybill.is_archived = False
        waybill.archived_at = None
        waybill.last_checked_at = synced_at
        if nova_poshta_account_id is not None:
            waybill.nova_poshta_account_id = nova_poshta_account_id
        await self._session.flush()
        await self._session.refresh(waybill)
        return waybill

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
        waybill.is_archived = False
        waybill.archived_at = None
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

    async def delete_waybill(self, waybill: Waybill) -> None:
        """Delete a waybill and its related order items."""
        await self._session.execute(delete(Waybill).where(Waybill.id == waybill.id))
        await self._session.flush()
