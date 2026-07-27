from __future__ import annotations

from typing import Any

from loguru import logger

from app.models.order_item import OrderItem
from app.models.waybill import Waybill
from app.nova_poshta import NovaPoshtaClient
from app.repositories.order_item_repository import OrderItemRepository
from app.repositories.recipient_repository import RecipientRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.ttn_service import (
    create_internet_document,
    extract_recipient_save_fields,
    format_phone_display,
)
from app.services.waybill_service import build_waybill_create_fields


def format_products_block(items: list[OrderItem]) -> str:
    """Format ordered products as a bullet list."""
    if not items:
        return "—"
    return "\n".join(f"• {item.product_name}" for item in items)


def format_waybill_details(
    index: int,
    waybill: Waybill,
    items: list[OrderItem],
) -> str:
    """Format a waybill order card for Telegram."""
    delivery_cost = waybill.delivery_cost or "—"
    return (
        f"№{index}\n\n"
        f"👤 {waybill.recipient_name}\n\n"
        f"📞 {format_phone_display(waybill.recipient_phone)}\n\n"
        f"🏙 {waybill.city_name}\n\n"
        f"🏢 №{waybill.warehouse_number}\n\n"
        f"🛍 Products\n\n"
        f"{format_products_block(items)}\n\n"
        f"💰 COD: {waybill.cod_amount}\n\n"
        f"📄 TTN: {waybill.ttn_number}\n\n"
        f"🚚 Shipping cost: {delivery_cost}"
    )


async def create_ttn_with_order_items(
    *,
    telegram_user_id: int,
    wizard_data: dict[str, Any],
    sender_profile: dict[str, str],
    product_names: list[str],
    api_key: str,
    recipient_repository: RecipientRepository,
    waybill_repository: WaybillRepository,
    order_item_repository: OrderItemRepository,
    save_recipient: bool = False,
) -> tuple[dict[str, Any], Waybill]:
    """Create a TTN, persist the order, and attach product lines."""
    async with NovaPoshtaClient(api_key) as client:
        document = await create_internet_document(
            client,
            wizard_data,
            sender_profile,
        )

    if save_recipient:
        await recipient_repository.save_recipient(
            telegram_user_id=telegram_user_id,
            **extract_recipient_save_fields(wizard_data),
        )

    waybill = await waybill_repository.create_waybill(
        **build_waybill_create_fields(
            telegram_user_id=telegram_user_id,
            document=document,
            wizard_data=wizard_data,
        ),
    )
    await order_item_repository.create_items(waybill.id, product_names)
    logger.info(
        "Saved order {} with {} products for user {}",
        waybill.ttn_number,
        len(product_names),
        telegram_user_id,
    )
    return document, waybill
