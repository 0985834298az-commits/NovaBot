from __future__ import annotations

from datetime import datetime
from typing import Any

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
        return parts[0], parts[1], ""
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
) -> dict[str, str]:
    """Build InternetDocument.save payload from wizard data."""
    sender_city = wizard_data["sender_city"]
    sender_warehouse = wizard_data["sender_warehouse"]
    recipient_city = wizard_data["recipient_city"]
    recipient_warehouse = wizard_data["recipient_warehouse"]

    return {
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


def build_print_link(document_ref: str, api_key: str) -> str:
    """Build a printable PDF link for a created document."""
    return PRINT_DOCUMENT_URL.format(document_ref=document_ref, api_key=api_key)


def format_ttn_success_message(
    *,
    ttn_number: str,
    reference: str,
    delivery_cost: str | float | int | None = None,
) -> str:
    """Format a success message for a created TTN."""
    lines = [
        "✅ ТТН успішно створено!\n",
        f"Номер: <b>{ttn_number}</b>",
        f"Reference: <code>{reference}</code>",
    ]
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


def format_review_text(wizard_data: dict[str, Any]) -> str:
    """Format wizard data for the review step."""
    sender_city = wizard_data["sender_city"]["name"]
    sender_warehouse = wizard_data["sender_warehouse"]["description"]
    recipient_city = wizard_data["recipient_city"]["name"]
    recipient_warehouse = wizard_data["recipient_warehouse"]["description"]

    return (
        "<b>Перевірте дані перед створенням ТТН</b>\n\n"
        f"<b>Відправник</b>\n"
        f"Місто: {sender_city}\n"
        f"Відділення: {sender_warehouse}\n\n"
        f"<b>Одержувач</b>\n"
        f"ПІБ: {wizard_data['recipient_name']}\n"
        f"Телефон: {wizard_data['recipient_phone']}\n"
        f"Місто: {recipient_city}\n"
        f"Відділення: {recipient_warehouse}\n\n"
        f"<b>Вантаж</b>\n"
        f"Опис: {wizard_data['cargo_description']}\n"
        f"Вага: {wizard_data['weight']} кг\n"
        f"Оціночна вартість: {wizard_data['declared_cost']} грн"
    )


def normalize_phone(phone: str) -> str | None:
    """Normalize Ukrainian phone numbers to 380XXXXXXXXX."""
    digits = "".join(char for char in phone if char.isdigit())
    if digits.startswith("380") and len(digits) == 12:
        return digits
    if digits.startswith("0") and len(digits) == 10:
        return f"38{digits}"
    return None


def parse_weight(value: str) -> str | None:
    """Validate cargo weight."""
    normalized = value.replace(",", ".").strip()
    try:
        weight = float(normalized)
    except ValueError:
        return None
    if weight <= 0:
        return None
    return f"{weight:g}"


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
