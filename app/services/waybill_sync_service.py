"""Two-way synchronization between local waybills and Nova Poshta."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger

from app.constants import TTN_DEFAULT_CARGO_DESCRIPTION, TTN_DEFAULT_DECLARED_COST, TTN_DEFAULT_WEIGHT
from app.models.nova_poshta_account import NovaPoshtaAccount
from app.models.waybill import Waybill
from app.nova_poshta import NovaPoshtaClient
from app.nova_poshta.constants import DOCUMENT_LIST_PAGE_SIZE, DOCUMENT_LIST_SYNC_DAYS
from app.nova_poshta.exceptions import NovaPoshtaError
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.waybill_repository import WaybillRepository
from app.utils.waybill_status import format_status_label, normalize_status_code


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


def _format_np_date(value: datetime) -> str:
    return value.strftime("%d.%m.%Y")


def _first_value(document: dict[str, Any], *keys: str) -> str:
    for key in keys:
        raw = document.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            return text
    return ""


def _extract_cod_amount(document: dict[str, Any]) -> str:
    for key in (
        "AfterpaymentOnGoodsCost",
        "RedeliverySum",
        "RedeliveryPayment",
        "BackwardDeliveryMoney",
    ):
        value = _first_value(document, key)
        if value and value not in {"0", "0.0", "0,0"}:
            return value.replace(",", ".")

    backward = document.get("BackwardDeliveryData")
    if isinstance(backward, list):
        for item in backward:
            if not isinstance(item, dict):
                continue
            if str(item.get("CargoType") or "").casefold() == "money":
                amount = _first_value(item, "RedeliveryString", "Amount")
                if amount:
                    return amount.replace(",", ".")
    return "0"


def _extract_warehouse_number(document: dict[str, Any]) -> str:
    number = _first_value(document, "WarehouseRecipientNumber")
    if number:
        return number.lstrip("№")
    description = _first_value(document, "WarehouseRecipientDescription", "RecipientAddressDescription")
    for token in description.replace("№", " ").split():
        if token.isdigit():
            return token
    return ""


def _map_remote_document(document: dict[str, Any]) -> dict[str, str]:
    if _first_value(document, "DeletionMark") in {"1", "true", "True"}:
        status_code = "2"
    else:
        status_code = normalize_status_code(document.get("StateId") or document.get("StatusCode"))
    delivery_cost = _first_value(document, "CostOnSite", "DocumentCost") or None
    return {
        "ttn_number": _first_value(document, "IntDocNumber", "Number"),
        "document_ref": _first_value(document, "Ref"),
        "recipient_name": _first_value(
            document,
            "RecipientContactPerson",
            "RecipientDescription",
            "ContactRecipientDescription",
        ),
        "recipient_phone": _first_value(document, "RecipientsPhone", "RecipientPhone", "Phone"),
        "city_name": _first_value(document, "CityRecipientDescription", "RecipientCityName"),
        "city_ref": _first_value(document, "CityRecipient", "RecipientCityRef"),
        "warehouse_number": _extract_warehouse_number(document),
        "warehouse_ref": _first_value(document, "WarehouseRecipient", "WarehouseRecipientRef"),
        "cod_amount": _extract_cod_amount(document),
        "delivery_cost": delivery_cost,
        "cargo_description": _first_value(document, "Description") or TTN_DEFAULT_CARGO_DESCRIPTION,
        "weight": _first_value(document, "Weight") or TTN_DEFAULT_WEIGHT,
        "declared_cost": _first_value(document, "Cost") or TTN_DEFAULT_DECLARED_COST,
        "shipment_status_code": status_code,
        "shipment_status": format_status_label(status_code, document.get("Status")),
    }


def _documents_equal(local: Waybill, remote_fields: dict[str, str]) -> bool:
    comparable = (
        "ttn_number",
        "document_ref",
        "recipient_name",
        "recipient_phone",
        "city_name",
        "city_ref",
        "warehouse_number",
        "warehouse_ref",
        "cod_amount",
        "delivery_cost",
        "cargo_description",
        "weight",
        "declared_cost",
        "shipment_status",
        "shipment_status_code",
    )
    for key in comparable:
        local_value = getattr(local, key)
        remote_value = remote_fields.get(key)
        if key == "delivery_cost":
            local_text = str(local_value or "").strip()
            remote_text = str(remote_value or "").strip()
            if local_text != remote_text:
                return False
            continue
        if str(local_value or "").strip() != str(remote_value or "").strip():
            return False
    return True


async def _fetch_remote_documents(client: NovaPoshtaClient) -> list[dict[str, Any]]:
    now = datetime.now().astimezone()
    date_from = now - timedelta(days=DOCUMENT_LIST_SYNC_DAYS)
    documents: list[dict[str, Any]] = []
    page = 1

    while True:
        response = await client.get_document_list(
            date_time_from=_format_np_date(date_from),
            date_time_to=_format_np_date(now),
            page=str(page),
            limit=DOCUMENT_LIST_PAGE_SIZE,
        )
        if response.get("success") is not True:
            errors = [str(error) for error in response.get("errors") or []]
            msg = "; ".join(errors) or "Nova Poshta failed to return document list"
            logger.error(
                "Nova Poshta getDocumentList failed: DateTimeFrom={} DateTimeTo={} Page={} errors={} response={}",
                _format_np_date(date_from),
                _format_np_date(now),
                page,
                errors,
                response,
            )
            raise NovaPoshtaError(msg)

        batch = [item for item in response.get("data") or [] if isinstance(item, dict)]
        if not batch:
            break

        documents.extend(batch)
        if len(batch) < int(DOCUMENT_LIST_PAGE_SIZE):
            break
        page += 1

    return documents


async def _fetch_missing_documents(
    client: NovaPoshtaClient,
    waybills: list[Waybill],
    remote_by_ref: dict[str, dict[str, Any]],
    remote_by_ttn: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    merged = dict(remote_by_ref)
    for waybill in waybills:
        if waybill.document_ref and waybill.document_ref in merged:
            continue
        if waybill.ttn_number in remote_by_ttn:
            continue

        lookup_ref = waybill.document_ref
        if not lookup_ref:
            continue

        response = await client.get_document(lookup_ref)
        if response.get("success") is not True:
            continue
        data = response.get("data")
        if isinstance(data, list) and data and isinstance(data[0], dict):
            document = data[0]
        elif isinstance(data, dict):
            document = data
        else:
            continue

        ref = _first_value(document, "Ref")
        ttn = _first_value(document, "IntDocNumber", "Number")
        if ref:
            merged[ref] = document
        if ttn:
            remote_by_ttn[ttn] = document
    return merged


async def sync_account_waybills(
    *,
    account: NovaPoshtaAccount,
    telegram_user_id: int,
    waybill_repository: WaybillRepository,
) -> SyncResult:
    """Synchronize one Nova Poshta account with the local database."""
    result = SyncResult()
    synced_at = datetime.now(UTC)
    logger.info(
        "Starting Nova Poshta sync for user {} account {} (id={}, active={})",
        telegram_user_id,
        account.account_name,
        account.id,
        account.is_active,
    )
    local_waybills = await waybill_repository.get_by_account_id(telegram_user_id, account.id)
    unassigned_waybills = await waybill_repository.get_unassigned(telegram_user_id)
    local_by_ref = {
        waybill.document_ref: waybill
        for waybill in (*local_waybills, *unassigned_waybills)
        if waybill.document_ref
    }
    local_by_ttn = {
        waybill.ttn_number: waybill for waybill in (*local_waybills, *unassigned_waybills)
    }

    async with NovaPoshtaClient(account.api_key) as client:
        remote_documents = await _fetch_remote_documents(client)
        remote_by_ref: dict[str, dict[str, Any]] = {}
        remote_by_ttn: dict[str, dict[str, Any]] = {}
        for document in remote_documents:
            ref = _first_value(document, "Ref")
            ttn = _first_value(document, "IntDocNumber", "Number")
            if ref:
                remote_by_ref[ref] = document
            if ttn:
                remote_by_ttn[ttn] = document

        remote_by_ref = await _fetch_missing_documents(
            client,
            local_waybills,
            remote_by_ref,
            remote_by_ttn,
        )

    seen_local_ids: set[int] = set()

    for document in remote_by_ref.values():
        fields = _map_remote_document(document)
        if not fields["ttn_number"]:
            continue

        waybill = None
        if fields["document_ref"]:
            waybill = local_by_ref.get(fields["document_ref"])
        if waybill is None:
            waybill = local_by_ttn.get(fields["ttn_number"])

        if waybill is None:
            await waybill_repository.create_waybill(
                telegram_user_id=telegram_user_id,
                nova_poshta_account_id=account.id,
                **fields,
            )
            result.added += 1
            logger.info(
                "Imported TTN {} for user {} account {}",
                fields["ttn_number"],
                telegram_user_id,
                account.account_name,
            )
            continue

        seen_local_ids.add(waybill.id)
        if _documents_equal(waybill, fields):
            continue

        await waybill_repository.update_from_sync(
            waybill,
            nova_poshta_account_id=account.id,
            synced_at=synced_at,
            **fields,
        )
        result.updated += 1
        logger.info(
            "Updated TTN {} for user {} account {}",
            fields["ttn_number"],
            telegram_user_id,
            account.account_name,
        )

    for waybill in local_waybills:
        if waybill.id in seen_local_ids:
            continue
        if waybill.document_ref and waybill.document_ref in remote_by_ref:
            continue
        if waybill.ttn_number in remote_by_ttn:
            continue

        await waybill_repository.delete_waybill(waybill)
        result.deleted += 1
        logger.info(
            "Deleted TTN {} for user {} account {} because it is missing in Nova Poshta",
            waybill.ttn_number,
            telegram_user_id,
            account.account_name,
        )

    return result


async def sync_user_waybills(
    *,
    telegram_user_id: int,
    account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
) -> SyncResult:
    """Synchronize the active Nova Poshta account for a Telegram user."""
    total = SyncResult()
    active_account = await account_repository.get_active_account(telegram_user_id)
    if active_account is None:
        logger.warning("Nova Poshta sync skipped for user {}: no active account", telegram_user_id)
        return total

    logger.info(
        "Nova Poshta sync using active account {} (id={}) for user {}",
        active_account.account_name,
        active_account.id,
        telegram_user_id,
    )

    try:
        account_result = await sync_account_waybills(
            account=active_account,
            telegram_user_id=telegram_user_id,
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
