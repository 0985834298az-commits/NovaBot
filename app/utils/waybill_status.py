"""Helpers for Nova Poshta waybill shipment statuses."""

from __future__ import annotations

from typing import Any

from app.constants import WAYBILL_DELETED_STATUS_CODES, WAYBILL_LIST_ACTIVE_STATUS_CODES

_STATUS_LABELS: dict[str, str] = {
    "1": "🟡 Створена",
    "2": "❌ Видалена",
    "3": "❌ Видалена",
    "4": "🚚 У дорозі",
    "5": "🚚 У дорозі",
    "6": "🚚 У дорозі",
    "7": "📦 Прибула у відділення",
    "8": "📦 Прибула у відділення",
    "9": "✅ Отримана",
    "10": "✅ Отримана",
    "11": "✅ Отримана",
    "14": "↩️ Повертається",
    "41": "🚚 У дорозі",
    "101": "↩️ Повертається",
    "102": "↩️ Повертається",
    "103": "✔️ Повернена",
    "104": "🚚 У дорозі",
    "105": "📦 Прибула у відділення",
    "106": "✔️ Повернена",
    "111": "↩️ Повертається",
}


def normalize_status_code(status_code: str | int | None) -> str:
    """Return a trimmed status code string."""
    if status_code is None:
        return "1"
    return str(status_code).strip() or "1"


def is_deleted_status(status_code: str | int | None) -> bool:
    """Return True when the TTN is deleted and must not count toward COD limits."""
    return normalize_status_code(status_code) in WAYBILL_DELETED_STATUS_CODES


def is_list_active_status(status_code: str | int | None) -> bool:
    """Return True when the TTN should appear in the My Waybills list."""
    return (
        normalize_status_code(status_code) in WAYBILL_LIST_ACTIVE_STATUS_CODES
    )


def is_created_status(status_code: str | int | None) -> bool:
    """Return True when the TTN is still waiting to be handed over."""
    return normalize_status_code(status_code) == "1"


def should_archive_status(status_code: str | int | None) -> bool:
    """Return True when Nova Poshta has accepted the shipment for delivery."""
    if status_code is None:
        return False
    return not is_created_status(status_code)


def format_status_label(
    status_code: str | int | None,
    fallback_status: str | None = None,
) -> str:
    """Map Nova Poshta status code to a user-facing Ukrainian label."""
    code = normalize_status_code(status_code)
    label = _STATUS_LABELS.get(code)
    if label is not None:
        return label
    if fallback_status and str(fallback_status).strip():
        return str(fallback_status).strip()
    return _STATUS_LABELS["1"]


def parse_status_documents(response: dict[str, Any]) -> list[dict[str, str]]:
    """Extract tracking results from TrackingDocument.getStatusDocuments."""
    if response.get("success") is not True:
        return []

    statuses: list[dict[str, str]] = []
    for item in response.get("data") or []:
        if not isinstance(item, dict):
            continue
        number = str(item.get("Number") or item.get("DocumentNumber") or "").strip()
        if not number:
            continue
        status_code = normalize_status_code(item.get("StatusCode"))
        statuses.append(
            {
                "number": number,
                "status": format_status_label(status_code, item.get("Status")),
                "status_code": status_code,
            },
        )
    return statuses
