from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.constants import (
    TTN_DEFAULT_CARGO_DESCRIPTION,
    TTN_DEFAULT_DECLARED_COST,
    TTN_DEFAULT_WEIGHT,
)
from app.nova_poshta.client import NovaPoshtaClient
from app.nova_poshta.constants import PRINT_DOCUMENT_URL
from app.nova_poshta.exceptions import NovaPoshtaApiError


def parse_settlements(response: dict[str, Any]) -> list[dict[str, str]]:
    """Extract settlement options from searchSettlements response."""
    if response.get("success") is not True:
        return []

    settlements: list[dict[str, str]] = []
    for block in response.get("data") or []:
        for item in block.get("Addresses") or []:
            name = item.get("Present") or item.get("MainDescription") or ""
            if not name:
                continue
            settlements.append(
                {
                    "ref": str(item.get("Ref") or ""),
                    "delivery_city": str(item.get("DeliveryCity") or item.get("Ref") or ""),
                    "name": str(name),
                    "area": str(item.get("Area") or ""),
                    "region": str(item.get("Region") or ""),
                    "settlement_type": str(item.get("SettlementTypeCode") or ""),
                },
            )
    return settlements


def parse_warehouses(response: dict[str, Any]) -> list[dict[str, str]]:
    """Extract warehouse options from getWarehouses response."""
    if response.get("success") is not True:
        return []

    warehouses: list[dict[str, str]] = []
    for item in response.get("data") or []:
        description = str(item.get("Description") or "")
        number = str(item.get("Number") or "")
        if not description and not number:
            continue
        warehouses.append(
            {
                "ref": str(item.get("Ref") or ""),
                "number": number,
                "description": description,
            },
        )
    return warehouses


@dataclass(frozen=True, slots=True)
class TtnOrderInput:
    """Parsed single-message TTN order."""

    recipient_name: str
    recipient_phone: str
    city_query: str
    warehouse_number: str
    cod_amount: str


def parse_ttn_order_message(text: str) -> TtnOrderInput | None:
    """Parse a five-line TTN order message."""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if len(lines) != 5:
        return None

    phone = normalize_phone(lines[1])
    cod_amount = parse_declared_cost(lines[4])
    if phone is None or cod_amount is None:
        return None

    return TtnOrderInput(
        recipient_name=lines[0],
        recipient_phone=phone,
        city_query=lines[2],
        warehouse_number=lines[3].strip().lstrip("№"),
        cod_amount=cod_amount,
    )


def find_best_settlement(
    settlements: list[dict[str, str]],
    query: str,
) -> dict[str, str] | None:
    """Pick the best settlement match for the provided query."""
    if not settlements:
        return None

    query_lower = query.casefold()
    for settlement in settlements:
        if query_lower in settlement["name"].casefold():
            return settlement

    return settlements[0]


def find_warehouse_by_number(
    warehouses: list[dict[str, str]],
    number: str,
) -> dict[str, str] | None:
    """Find a warehouse by its branch number."""
    normalized = number.strip().lstrip("№")
    for warehouse in warehouses:
        if warehouse["number"] == normalized:
            return warehouse
    return None


async def fetch_sender_location(
    client: NovaPoshtaClient,
    sender_ref: str,
) -> dict[str, dict[str, str]]:
    """Load the sender city and warehouse from counterparty addresses."""
    response = await client.get_counterparty_addresses(sender_ref)
    if response.get("success") is not True:
        errors = [str(error) for error in response.get("errors") or []]
        msg = "; ".join(errors) or "Failed to load sender addresses"
        raise NovaPoshtaApiError(msg, errors=errors)

    addresses = response.get("data") or []
    for address in addresses:
        if not isinstance(address, dict):
            continue

        warehouse_ref = str(address.get("Ref") or "")
        city_ref = str(address.get("CityRef") or address.get("DeliveryCity") or "")
        if not warehouse_ref or not city_ref:
            continue

        return {
            "sender_city": {"delivery_city": city_ref},
            "sender_warehouse": {
                "ref": warehouse_ref,
                "number": str(address.get("WarehouseIndex") or address.get("Number") or ""),
                "description": str(address.get("Description") or address.get("Address") or ""),
            },
        }

    msg = "Sender warehouse address was not found for this API key"
    raise NovaPoshtaApiError(msg)


async def prepare_wizard_data_from_order(
    client: NovaPoshtaClient,
    order: TtnOrderInput,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Resolve API data required to create a TTN from a parsed order."""
    sender_profile = await fetch_sender_profile(client)
    sender_location = await fetch_sender_location(client, sender_profile["ref"])

    city_response = await client.search_settlements(order.city_query)
    settlements = parse_settlements(city_response)
    recipient_city = find_best_settlement(settlements, order.city_query)
    if recipient_city is None:
        msg = "Recipient city was not found"
        raise NovaPoshtaApiError(msg)

    warehouse_response = await client.get_warehouses(
        recipient_city["delivery_city"],
        find_by_string=order.warehouse_number,
    )
    warehouses = parse_warehouses(warehouse_response)
    recipient_warehouse = find_warehouse_by_number(warehouses, order.warehouse_number)
    if recipient_warehouse is None:
        msg = "Recipient warehouse was not found"
        raise NovaPoshtaApiError(msg)

    return {
        **sender_location,
        "recipient_name": order.recipient_name,
        "recipient_phone": order.recipient_phone,
        "recipient_city": recipient_city,
        "recipient_warehouse": recipient_warehouse,
        "cargo_description": TTN_DEFAULT_CARGO_DESCRIPTION,
        "weight": TTN_DEFAULT_WEIGHT,
        "declared_cost": TTN_DEFAULT_DECLARED_COST,
        "cod_amount": order.cod_amount,
    }, sender_profile


async def create_internet_document(
    client: NovaPoshtaClient,
    wizard_data: dict[str, Any],
    sender_profile: dict[str, str],
) -> dict[str, Any]:
    """Create a TTN using collected wizard data."""
    recipient_profile = await fetch_or_create_recipient_profile(client, wizard_data)
    save_properties = build_save_properties(
        wizard_data,
        sender_profile,
        recipient_profile,
    )
    response = await client.save_internet_document(save_properties)
    return extract_created_document(response)


async def fetch_sender_profile(client: NovaPoshtaClient) -> dict[str, str]:
    """Load sender counterparty and default contact for TTN creation."""
    response = await client.get_sender_counterparties()
    if response.get("success") is not True:
        errors = [str(error) for error in response.get("errors") or []]
        msg = "; ".join(errors) or "Failed to load sender profile"
        raise NovaPoshtaApiError(msg, errors=errors)

    counterparties = response.get("data") or []
    if not counterparties:
        msg = "Sender counterparty was not found for this API key"
        raise NovaPoshtaApiError(msg)

    counterparty = counterparties[0]
    contacts_response = await client.get_counterparty_contact_persons(
        str(counterparty["Ref"]),
    )
    if contacts_response.get("success") is not True:
        errors = [str(error) for error in contacts_response.get("errors") or []]
        msg = "; ".join(errors) or "Failed to load sender contact"
        raise NovaPoshtaApiError(msg, errors=errors)

    contacts = contacts_response.get("data") or []
    if not contacts:
        msg = "Sender contact person was not found"
        raise NovaPoshtaApiError(msg)

    contact = contacts[0]
    phone = str(contact.get("Phones") or contact.get("Phone") or "")
    return {
        "ref": str(counterparty["Ref"]),
        "contact_ref": str(contact["Ref"]),
        "phone": phone,
        "description": str(counterparty.get("Description") or ""),
    }


def parse_recipient_name(full_name: str) -> tuple[str, str, str]:
    """Split recipient full name into last, first, and middle names."""
    parts = [part for part in full_name.split() if part]
    if len(parts) >= 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[1], parts[0], ""
    if len(parts) == 1:
        return parts[0], parts[0], ""
    return "Одержувач", "Одержувач", ""


def _extract_contact_ref(counterparty: dict[str, Any]) -> str:
    contacts = counterparty.get("ContactPerson") or counterparty.get("ContactPersons") or []
    if isinstance(contacts, list) and contacts:
        contact = contacts[0]
        if isinstance(contact, dict):
            return str(contact.get("Ref") or "")
    return ""


async def _load_recipient_contacts(
    client: NovaPoshtaClient,
    counterparty_ref: str,
) -> list[dict[str, Any]]:
    contacts_response = await client.get_counterparty_contact_persons(counterparty_ref)
    if contacts_response.get("success") is not True:
        errors = [str(error) for error in contacts_response.get("errors") or []]
        msg = "; ".join(errors) or "Failed to load recipient contact"
        raise NovaPoshtaApiError(msg, errors=errors)

    contacts = contacts_response.get("data") or []
    return [contact for contact in contacts if isinstance(contact, dict)]


async def fetch_or_create_recipient_profile(
    client: NovaPoshtaClient,
    wizard_data: dict[str, Any],
) -> dict[str, str]:
    """Load or create recipient counterparty and contact person."""
    phone = str(wizard_data["recipient_phone"])
    recipient_city = wizard_data["recipient_city"]
    last_name, first_name, middle_name = parse_recipient_name(
        str(wizard_data["recipient_name"]),
    )
    city_ref = str(recipient_city["delivery_city"])

    catalog_response = await client.get_catalog_counterparty(phone)
    if catalog_response.get("success") is True:
        catalog_data = catalog_response.get("data") or []
        if catalog_data:
            counterparty = catalog_data[0]
            counterparty_ref = str(counterparty.get("Ref") or "")
            contact_ref = _extract_contact_ref(counterparty)
            if counterparty_ref and not contact_ref:
                contacts = await _load_recipient_contacts(client, counterparty_ref)
                if contacts:
                    contact_ref = str(contacts[0].get("Ref") or "")
            if counterparty_ref and contact_ref:
                return {
                    "ref": counterparty_ref,
                    "contact_ref": contact_ref,
                    "phone": phone,
                }

    save_response = await client.save_recipient_counterparty(
        first_name=first_name,
        last_name=last_name,
        middle_name=middle_name,
        phone=phone,
        city_ref=city_ref,
    )
    if save_response.get("success") is not True:
        errors = [str(error) for error in save_response.get("errors") or []]
        msg = "; ".join(errors) or "Failed to create recipient counterparty"
        raise NovaPoshtaApiError(msg, errors=errors)

    counterparty = (save_response.get("data") or [{}])[0]
    counterparty_ref = str(counterparty.get("Ref") or "")
    contact_ref = _extract_contact_ref(counterparty)

    if counterparty_ref and not contact_ref:
        contacts = await _load_recipient_contacts(client, counterparty_ref)
        if contacts:
            contact_ref = str(contacts[0].get("Ref") or "")

    if counterparty_ref and not contact_ref:
        contact_response = await client.save_contact_person(
            counterparty_ref=counterparty_ref,
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            phone=phone,
        )
        if contact_response.get("success") is not True:
            errors = [str(error) for error in contact_response.get("errors") or []]
            msg = "; ".join(errors) or "Failed to create recipient contact person"
            raise NovaPoshtaApiError(msg, errors=errors)

        contact = (contact_response.get("data") or [{}])[0]
        contact_ref = str(contact.get("Ref") or "")

    if not counterparty_ref or not contact_ref:
        msg = "Recipient counterparty was created without required refs"
        raise NovaPoshtaApiError(msg)

    return {
        "ref": counterparty_ref,
        "contact_ref": contact_ref,
        "phone": phone,
    }


def build_save_properties(
    wizard_data: dict[str, Any],
    sender_profile: dict[str, str],
    recipient_profile: dict[str, str],
) -> dict[str, Any]:
    """Build InternetDocument.save payload from wizard data."""
    sender_city = wizard_data["sender_city"]
    sender_warehouse = wizard_data["sender_warehouse"]
    recipient_city = wizard_data["recipient_city"]
    recipient_warehouse = wizard_data["recipient_warehouse"]

    properties: dict[str, Any] = {
        "PayerType": "Sender",
        "PaymentMethod": "Cash",
        "DateTime": datetime.now().strftime("%d.%m.%Y"),
        "CargoType": "Cargo",
        "Weight": str(wizard_data["weight"]),
        "ServiceType": "WarehouseWarehouse",
        "SeatsAmount": "1",
        "Description": str(wizard_data["cargo_description"]),
        "Cost": str(wizard_data["declared_cost"]),
        "CitySender": str(sender_city["delivery_city"]),
        "CityRecipient": str(recipient_city["delivery_city"]),
        "Sender": sender_profile["ref"],
        "SenderAddress": str(sender_warehouse["ref"]),
        "ContactSender": sender_profile["contact_ref"],
        "SendersPhone": sender_profile["phone"],
        "Recipient": recipient_profile["ref"],
        "RecipientAddress": str(recipient_warehouse["ref"]),
        "ContactRecipient": recipient_profile["contact_ref"],
        "RecipientsPhone": recipient_profile["phone"],
    }

    cod_amount = wizard_data.get("cod_amount")
    if cod_amount:
        properties["BackwardDeliveryData"] = [
            {
                "PayerType": "Recipient",
                "CargoType": "Money",
                "RedeliveryString": str(cod_amount),
            },
        ]

    return properties


def build_print_link(document_ref: str, api_key: str) -> str:
    """Build a printable PDF link for a created document."""
    return PRINT_DOCUMENT_URL.format(document_ref=document_ref, api_key=api_key)


def format_ttn_success_message(
    *,
    ttn_number: str,
    delivery_cost: str | float | int | None = None,
) -> str:
    """Format a success message for a created TTN."""
    lines = [f"✅ ТТН: <b>{ttn_number}</b>"]
    if delivery_cost is not None and str(delivery_cost).strip() not in {"", "—"}:
        lines.append(f"Вартість доставки: {delivery_cost} грн")
    return "\n".join(lines)


def extract_created_document(response: dict[str, Any]) -> dict[str, Any]:
    """Return the created document payload from InternetDocument.save."""
    data = response.get("data") or []
    if not data:
        return {}
    document = data[0]
    if isinstance(document, dict):
        return document
    return {}


def normalize_phone(phone: str) -> str | None:
    """Normalize Ukrainian phone numbers to 380XXXXXXXXX."""
    digits = "".join(char for char in phone if char.isdigit())
    if digits.startswith("380") and len(digits) == 12:
        return digits
    if digits.startswith("0") and len(digits) == 10:
        return f"38{digits}"
    return None


def parse_declared_cost(value: str) -> str | None:
    """Validate declared cost."""
    normalized = value.replace(",", ".").strip()
    try:
        cost = float(normalized)
    except ValueError:
        return None
    if cost <= 0:
        return None
    if cost.is_integer():
        return str(int(cost))
    return f"{cost:g}"
