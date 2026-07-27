from __future__ import annotations

from typing import Any


def build_waybill_create_fields(
    *,
    telegram_user_id: int,
    document: dict[str, Any],
    wizard_data: dict[str, Any],
    nova_poshta_account_id: int | None = None,
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
        "nova_poshta_account_id": nova_poshta_account_id,
    }
