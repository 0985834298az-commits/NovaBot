from __future__ import annotations

from typing import Any

from app.models.waybill import Waybill


def build_waybill_create_fields(
    *,
    telegram_user_id: int,
    document: dict[str, Any],
    wizard_data: dict[str, Any],
) -> dict[str, Any]:
    """Extract persisted waybill fields from a created TTN."""
    recipient_city = wizard_data["recipient_city"]
    recipient_warehouse = wizard_data["recipient_warehouse"]
    delivery_cost = document.get("CostOnSite") or document.get("DocumentCost")

    return {
        "telegram_user_id": telegram_user_id,
        "ttn_number": str(document.get("IntDocNumber") or ""),
        "document_ref": str(document.get("Ref") or ""),
        "recipient_name": str(wizard_data["recipient_name"]),
        "recipient_phone": str(wizard_data["recipient_phone"]),
        "city_name": str(recipient_city["name"]),
        "city_ref": str(recipient_city["delivery_city"]),
        "warehouse_number": str(recipient_warehouse["number"]),
        "warehouse_ref": str(recipient_warehouse["ref"]),
        "cod_amount": str(wizard_data.get("cod_amount") or ""),
        "delivery_cost": str(delivery_cost) if delivery_cost is not None else None,
        "cargo_description": str(wizard_data["cargo_description"]),
        "weight": str(wizard_data["weight"]),
        "declared_cost": str(wizard_data["declared_cost"]),
    }


def format_active_waybill_line(index: int, waybill: Waybill) -> str:
    """Format one active waybill row with a dynamic display number."""
    return f"№{index} {waybill.recipient_name}"


def format_active_waybills_message(waybills: list[Waybill]) -> str:
    """Format the active waybills list for Telegram."""
    lines = [
        format_active_waybill_line(index, waybill)
        for index, waybill in enumerate(waybills, start=1)
    ]
    return "\n\n".join(lines)
