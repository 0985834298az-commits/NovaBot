"""Helpers for Nova Poshta waybill shipment statuses."""

from typing import Any


def is_created_status(status_code: str | int | None) -> bool:
    """Return True when the TTN is still waiting to be handed over."""
    if status_code is None:
        return True
    return str(status_code).strip() == "1"


def should_archive_status(status_code: str | int | None) -> bool:
    """Return True when Nova Poshta has accepted the shipment for delivery."""
    if status_code is None:
        return False
    return not is_created_status(status_code)


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
        statuses.append(
            {
                "number": number,
                "status": str(item.get("Status") or "").strip(),
                "status_code": str(item.get("StatusCode") or "").strip(),
            },
        )
    return statuses
