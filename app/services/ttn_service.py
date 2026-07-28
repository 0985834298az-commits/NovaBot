from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger

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


async def prepare_wizard_data_from_order(
    client: NovaPoshtaClient,
    order: TtnOrderInput,
    sender_location: dict[str, dict[str, str]],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Resolve API data required to create a TTN from a parsed order."""
    sender_profile = await fetch_sender_profile(client)

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


def build_wizard_data_from_saved_recipient(
    recipient: Any,
    cod_amount: str,
    sender_location: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Build TTN wizard data from a saved recipient record."""
    return {
        **sender_location,
        "recipient_name": recipient.full_name,
        "recipient_phone": recipient.phone,
        "recipient_city": {
            "ref": recipient.city_ref,
            "delivery_city": recipient.city_ref,
            "name": recipient.city_name,
            "area": "",
            "region": "",
            "settlement_type": "",
        },
        "recipient_warehouse": {
            "ref": recipient.warehouse_ref,
            "number": recipient.warehouse_number,
            "description": f"№{recipient.warehouse_number}",
        },
        "cargo_description": TTN_DEFAULT_CARGO_DESCRIPTION,
        "weight": TTN_DEFAULT_WEIGHT,
        "declared_cost": TTN_DEFAULT_DECLARED_COST,
        "cod_amount": cod_amount,
    }


def extract_recipient_save_fields(wizard_data: dict[str, Any]) -> dict[str, str]:
    """Extract recipient address book fields from wizard data."""
    recipient_city = wizard_data["recipient_city"]
    recipient_warehouse = wizard_data["recipient_warehouse"]
    return {
        "full_name": str(wizard_data["recipient_name"]),
        "phone": str(wizard_data["recipient_phone"]),
        "city_name": str(recipient_city["name"]),
        "city_ref": str(recipient_city["delivery_city"]),
        "warehouse_number": str(recipient_warehouse["number"]),
        "warehouse_ref": str(recipient_warehouse["ref"]),
    }


async def resolve_recipient_city_and_warehouse(
    client: NovaPoshtaClient,
    *,
    city_query: str,
    warehouse_number: str,
) -> tuple[dict[str, str], dict[str, str]]:
    """Resolve recipient city and warehouse refs from user input."""
    city_response = await client.search_settlements(city_query)
    settlements = parse_settlements(city_response)
    recipient_city = find_best_settlement(settlements, city_query)
    if recipient_city is None:
        msg = "Recipient city was not found"
        raise NovaPoshtaApiError(msg)

    warehouse_response = await client.get_warehouses(
        recipient_city["delivery_city"],
        find_by_string=warehouse_number,
    )
    warehouses = parse_warehouses(warehouse_response)
    recipient_warehouse = find_warehouse_by_number(warehouses, warehouse_number)
    if recipient_warehouse is None:
        msg = "Recipient warehouse was not found"
        raise NovaPoshtaApiError(msg)

    return recipient_city, recipient_warehouse


def format_phone_display(phone: str) -> str:
    """Format stored phone numbers for display."""
    normalized = normalize_phone(phone)
    if normalized is None:
        return phone
    if normalized.startswith("380") and len(normalized) == 12:
        return f"0{normalized[3:]}"
    return normalized


def format_recipient_card(recipient: Any) -> str:
    """Format a saved recipient for Telegram display."""
    return (
        f"👤 {recipient.full_name}\n"
        f"📞 {format_phone_display(recipient.phone)}\n"
        f"🏙 {recipient.city_name}\n"
        f"🏢 №{recipient.warehouse_number}"
    )


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
    use_cash2card = bool(wizard_data.get("cash2card_save_extras"))
    logger.info(
        "InternetDocument.save payload: {}",
        json.dumps(save_properties, ensure_ascii=False),
    )
    response = await client.save_internet_document(
        save_properties,
        use_cash2card=use_cash2card,
    )
    if use_cash2card:
        from app.services.cash2card_service import log_cash2card_block

        log_cash2card_block(
            entered_pan=str(wizard_data.get("payment_card_number") or ""),
            payout_id=str(wizard_data.get("cash2card_payout_id") or ""),
            backward_delivery_data=list(
                wizard_data.get("cash2card_backward_delivery_data") or [],
            ),
            save_payload=save_properties,
            save_response=response,
        )
    document = extract_created_document(response)
    logger.info(
        (
            "Created TTN recipient verification: entered_name={} entered_phone={} "
            "RecipientRef={} ContactPersonRef={} document_recipient={} document_phone={}"
        ),
        wizard_data["recipient_name"],
        wizard_data["recipient_phone"],
        recipient_profile["ref"],
        recipient_profile["contact_ref"],
        _extract_document_recipient_name(document),
        document.get("RecipientsPhone") or document.get("RecipientPhone"),
    )
    return document


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


def format_phone_for_nova_poshta(phone: str) -> str:
    """Convert normalized phone numbers to Nova Poshta 0XXXXXXXXX format."""
    normalized = normalize_phone(phone)
    if normalized is None:
        return phone
    if normalized.startswith("380") and len(normalized) == 12:
        return f"0{normalized[3:]}"
    return normalized


def phones_match(phone_a: str | None, phone_b: str | None) -> bool:
    """Compare two phone numbers after normalization."""
    normalized_a = normalize_phone(str(phone_a or ""))
    normalized_b = normalize_phone(str(phone_b or ""))
    return normalized_a is not None and normalized_a == normalized_b


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


def _find_counterparty_by_phone(
    counterparties: list[dict[str, Any]],
    phone: str,
) -> dict[str, Any] | None:
    """Find a counterparty whose phone matches the entered value."""
    for counterparty in counterparties:
        if phones_match(str(counterparty.get("Phone") or ""), phone):
            return counterparty
    return None


def _find_contact_by_phone(
    contacts: list[dict[str, Any]],
    phone: str,
) -> dict[str, Any] | None:
    """Find a contact person whose phone matches the entered value."""
    for contact in contacts:
        contact_phone = contact.get("Phones") or contact.get("Phone")
        if phones_match(str(contact_phone or ""), phone):
            return contact
    return None


async def _search_recipient_counterparty(
    client: NovaPoshtaClient,
    *,
    phone: str,
    last_name: str,
) -> dict[str, Any] | None:
    """Search account recipients and catalog by phone."""
    np_phone = format_phone_for_nova_poshta(phone)

    recipients_response = await client.get_recipient_counterparties(
        find_by_string=np_phone,
    )
    if recipients_response.get("success") is True:
        matched = _find_counterparty_by_phone(
            recipients_response.get("data") or [],
            phone,
        )
        if matched is not None:
            return matched

    catalog_response = await client.get_catalog_counterparty(np_phone, last_name)
    if catalog_response.get("success") is True:
        matched = _find_counterparty_by_phone(
            catalog_response.get("data") or [],
            phone,
        )
        if matched is not None:
            return matched

    return None


async def _resolve_recipient_contact_ref(
    client: NovaPoshtaClient,
    *,
    counterparty_ref: str,
    phone: str,
) -> str:
    """Load the contact person Ref for a recipient counterparty."""
    contacts = await _load_recipient_contacts(client, counterparty_ref)
    matched_contact = _find_contact_by_phone(contacts, phone)
    if matched_contact is not None:
        contact_ref = str(matched_contact.get("Ref") or "")
        if contact_ref:
            return contact_ref

    if contacts:
        contact_ref = str(contacts[0].get("Ref") or "")
        if contact_ref:
            return contact_ref

    msg = "Contact person was not found for recipient counterparty"
    raise NovaPoshtaApiError(msg)


async def fetch_or_create_recipient_profile(
    client: NovaPoshtaClient,
    wizard_data: dict[str, Any],
) -> dict[str, str]:
    """Load or create recipient counterparty and contact person."""
    phone = str(wizard_data["recipient_phone"])
    recipient_name = str(wizard_data["recipient_name"])
    recipient_city = wizard_data["recipient_city"]
    last_name, first_name, middle_name = parse_recipient_name(recipient_name)
    city_ref = str(recipient_city["delivery_city"])
    np_phone = format_phone_for_nova_poshta(phone)

    logger.info(
        "Resolving TTN recipient: entered_name={} entered_phone={}",
        recipient_name,
        phone,
    )

    existing_counterparty = await _search_recipient_counterparty(
        client,
        phone=phone,
        last_name=last_name,
    )

    counterparty_ref = ""
    contact_ref = ""

    if existing_counterparty is not None:
        counterparty_ref = str(existing_counterparty.get("Ref") or "")
        if counterparty_ref:
            update_response = await client.update_recipient_counterparty(
                counterparty_ref=counterparty_ref,
                first_name=first_name,
                last_name=last_name,
                middle_name=middle_name,
                phone=np_phone,
                city_ref=city_ref,
            )
            if update_response.get("success") is True:
                contact_ref = await _resolve_recipient_contact_ref(
                    client,
                    counterparty_ref=counterparty_ref,
                    phone=phone,
                )
            else:
                logger.warning(
                    "Failed to update existing recipient counterparty, creating a new one: {}",
                    update_response.get("errors"),
                )
                counterparty_ref = ""
                contact_ref = ""

    if not counterparty_ref or not contact_ref:
        save_response = await client.save_recipient_counterparty(
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            phone=np_phone,
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
            contact_ref = await _resolve_recipient_contact_ref(
                client,
                counterparty_ref=counterparty_ref,
                phone=phone,
            )

        if not counterparty_ref or not contact_ref:
            msg = "Recipient counterparty was created without required refs"
            raise NovaPoshtaApiError(msg)

    logger.info(
        "TTN recipient resolved: entered_name={} entered_phone={} RecipientRef={} ContactPersonRef={}",
        recipient_name,
        phone,
        counterparty_ref,
        contact_ref,
    )

    return {
        "ref": counterparty_ref,
        "contact_ref": contact_ref,
        "phone": phone,
        "name": recipient_name,
    }


def _extract_document_recipient_name(document: dict[str, Any]) -> str:
    """Extract recipient name fields from InternetDocument.save response."""
    for key in (
        "RecipientContactPerson",
        "RecipientDescription",
        "RecipientName",
        "ContactRecipientDescription",
    ):
        value = document.get(key)
        if value:
            return str(value)
    return ""


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
    cash2card_backward = wizard_data.get("cash2card_backward_delivery_data")
    cash2card_extras = wizard_data.get("cash2card_save_extras")
    if cod_amount and cash2card_backward and cash2card_extras:
        properties["BackwardDeliveryData"] = list(cash2card_backward)
        properties.update(dict(cash2card_extras))
        logger.info(
            "COD Cash2Card payout: payout_id={} masked_pan={} backward_delivery_data={}",
            wizard_data.get("cash2card_payout_id"),
            wizard_data.get("cash2card_masked_pan"),
            properties["BackwardDeliveryData"],
        )
    elif cod_amount:
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
