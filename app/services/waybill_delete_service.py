"""Delete TTN shipments through Nova Poshta and the local database."""

from __future__ import annotations

from loguru import logger

from app.models.waybill import Waybill
from app.nova_poshta import NovaPoshtaClient
from app.nova_poshta.exceptions import NovaPoshtaError
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.waybill_repository import WaybillRepository


async def _resolve_account(
    *,
    waybill: Waybill,
    telegram_user_id: int,
    account_repository: NovaPoshtaAccountRepository,
):
    if waybill.nova_poshta_account_id is not None:
        account = await account_repository.get_by_id(
            waybill.nova_poshta_account_id,
            telegram_user_id,
        )
        if account is not None:
            return account
    return await account_repository.get_active_account(telegram_user_id)


async def delete_waybill_shipment(
    *,
    waybill: Waybill,
    telegram_user_id: int,
    account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
) -> None:
    """Delete a TTN in Nova Poshta and remove it locally."""
    account = await _resolve_account(
        waybill=waybill,
        telegram_user_id=telegram_user_id,
        account_repository=account_repository,
    )
    if account is None:
        raise NovaPoshtaError("Не налаштовано жодного акаунта Нової Пошти.")

    document_ref = waybill.document_ref.strip()
    if not document_ref:
        raise NovaPoshtaError("Посилання на документ Nova Poshta відсутнє.")

    async with NovaPoshtaClient(account.api_key) as client:
        await client.delete_internet_document(document_ref)

    await waybill_repository.delete_waybill(waybill)
    logger.info(
        "Deleted TTN {} for user {} through Nova Poshta account {}",
        waybill.ttn_number,
        telegram_user_id,
        account.account_name,
    )
