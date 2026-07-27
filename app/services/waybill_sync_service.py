"""Synchronize local shipment statuses with Nova Poshta tracking API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from loguru import logger

from app.models.nova_poshta_account import NovaPoshtaAccount
from app.models.waybill import Waybill
from app.nova_poshta import NovaPoshtaClient
from app.nova_poshta.exceptions import NovaPoshtaError
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.waybill_repository import WaybillRepository
from app.utils.waybill_status import (
    filter_list_active_waybills,
    format_status_label,
    is_deleted_status,
    parse_status_documents,
)

TRACKING_BATCH_SIZE = 100


@dataclass(slots=True)
class SyncResult:
    """Aggregated synchronization counters."""

    added: int = 0
    updated: int = 0
    deleted: int = 0
    failed_accounts: list[str] = field(default_factory=list)

    def merge(self, other: SyncResult) -> None:
        self.added += other.added
        self.updated += other.updated
        self.deleted += other.deleted
        self.failed_accounts.extend(other.failed_accounts)


def _chunk_waybills(waybills: list[Waybill], size: int) -> list[list[Waybill]]:
    return [waybills[index : index + size] for index in range(0, len(waybills), size)]


def _is_not_found_error(response: dict[str, object], ttn_number: str) -> bool:
    """Return True when Nova Poshta explicitly reports a missing document."""
    markers = (
        "not found",
        "не знайден",
        "does not exist",
        "document number is incorrect",
        "номер документу",
    )
    for error in response.get("errors") or []:
        text = str(error).casefold()
        if ttn_number in str(error) and any(marker in text for marker in markers):
            return True
    return False


def _deleted_status_fields() -> tuple[str, str]:
    return "2", format_status_label("2")


async def _sync_active_shipments(
    *,
    account: NovaPoshtaAccount,
    telegram_user_id: int,
    active_shipments: list[Waybill],
    waybill_repository: WaybillRepository,
) -> SyncResult:
    """Update statuses for locally active shipments via TrackingDocument.getStatusDocuments."""
    result = SyncResult()
    if not active_shipments:
        return result

    synced_at = datetime.now(UTC)
    logger.info(
        "Starting tracking sync for user {} account {} (id={}, shipments={})",
        telegram_user_id,
        account.account_name,
        account.id,
        len(active_shipments),
    )

    async with NovaPoshtaClient(account.api_key) as client:
        for batch in _chunk_waybills(active_shipments, TRACKING_BATCH_SIZE):
            documents = [
                {
                    "DocumentNumber": waybill.ttn_number,
                    "Phone": waybill.recipient_phone,
                }
                for waybill in batch
            ]
            response = await client.get_status_documents(documents)
            if response.get("success") is not True:
                errors = [str(error) for error in response.get("errors") or []]
                msg = "; ".join(errors) or "Nova Poshta failed to return tracking statuses"
                logger.error(
                    "Nova Poshta getStatusDocuments failed for user {} account {}: {}",
                    telegram_user_id,
                    account.account_name,
                    response,
                )
                raise NovaPoshtaError(msg)

            statuses = parse_status_documents(response)
            status_by_number = {status["number"]: status for status in statuses}

            for waybill in batch:
                old_status = waybill.shipment_status
                old_status_code = waybill.shipment_status_code
                tracking = status_by_number.get(waybill.ttn_number)

                if tracking is not None:
                    api_status = tracking["status"]
                    new_status_code = tracking["status_code"]
                    new_status = format_status_label(new_status_code, api_status)
                elif _is_not_found_error(response, waybill.ttn_number):
                    new_status_code, new_status = _deleted_status_fields()
                    api_status = "NOT_FOUND"
                else:
                    api_status = "NOT_RETURNED"
                    logger.info(
                        "Sync status skipped: TTN={} -> API status={} -> Old status={} -> New status={}",
                        waybill.ttn_number,
                        api_status,
                        old_status,
                        old_status,
                    )
                    waybill.last_checked_at = synced_at
                    continue

                logger.info(
                    "Sync status update: TTN={} -> API status={} -> Old status={} -> New status={}",
                    waybill.ttn_number,
                    api_status,
                    old_status,
                    new_status,
                )

                if (
                    new_status_code == old_status_code
                    and new_status == old_status
                ):
                    waybill.last_checked_at = synced_at
                    continue

                await waybill_repository.update_tracking_status(
                    waybill,
                    shipment_status=new_status,
                    shipment_status_code=new_status_code,
                    last_checked_at=synced_at,
                )

                if is_deleted_status(new_status_code) and not is_deleted_status(old_status_code):
                    result.deleted += 1
                else:
                    result.updated += 1

    return result


async def sync_user_waybills(
    *,
    telegram_user_id: int,
    account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
) -> SyncResult:
    """Synchronize locally active shipments using Nova Poshta tracking API."""
    total = SyncResult()
    active_account = await account_repository.get_active_account(telegram_user_id)
    if active_account is None:
        logger.warning("Nova Poshta sync skipped for user {}: no active account", telegram_user_id)
        return total

    all_waybills = await waybill_repository.get_all_for_user(telegram_user_id)
    active_shipments = filter_list_active_waybills(all_waybills)
    if not active_shipments:
        logger.info("Nova Poshta sync skipped for user {}: no locally active shipments", telegram_user_id)
        return total

    logger.info(
        "Nova Poshta sync using active account {} (id={}) for user {} with {} active shipment(s)",
        active_account.account_name,
        active_account.id,
        telegram_user_id,
        len(active_shipments),
    )

    try:
        account_result = await _sync_active_shipments(
            account=active_account,
            telegram_user_id=telegram_user_id,
            active_shipments=active_shipments,
            waybill_repository=waybill_repository,
        )
        total.merge(account_result)
    except NovaPoshtaError:
        logger.exception(
            "Nova Poshta sync failed for user {} account {} (id={}, active={})",
            telegram_user_id,
            active_account.account_name,
            active_account.id,
            active_account.is_active,
        )
        total.failed_accounts.append(active_account.account_name)
    except Exception:
        logger.exception(
            "Unexpected sync failure for user {} account {} (id={}, active={})",
            telegram_user_id,
            active_account.account_name,
            active_account.id,
            active_account.is_active,
        )
        total.failed_accounts.append(active_account.account_name)

    return total
