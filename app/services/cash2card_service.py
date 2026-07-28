"""Cash2Card payout preparation for Nova Poshta TTN creation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.nova_poshta.client import NovaPoshtaClient
from app.nova_poshta.exceptions import NovaPoshtaApiError
from app.services.np_oauth_service import NpOAuthService
from app.services.payout_iframe_client import (
    PayoutCardRegistration,
    register_payout_card,
)
from app.services.ttn_service import normalize_phone
from app.utils.payment_card import mask_card_number, validate_card_number


@dataclass(frozen=True, slots=True)
class Cash2CardContext:
    """Resolved Cash2Card data ready for InternetDocument.save."""

    entered_pan: str
    payout_id: str
    masked_pan: str
    alias: str
    int_doc_number: str
    backward_delivery_data: list[dict[str, Any]]
    save_extras: dict[str, Any]


def build_backward_delivery_data(
    *,
    cod_amount: str | float | int,
    payout_id: str,
    masked_pan: str,
    alias: str = "",
) -> list[dict[str, Any]]:
    """Build BackwardDeliveryData exactly like the Nova Poshta business cabinet."""
    return [
        {
            "PayerType": "Recipient",
            "CargoType": "Money",
            "RedeliveryString": str(cod_amount),
            "Cash2CardPayout_Id": payout_id,
            "Cash2CardAlias": alias or "Картка",
            "Cash2CardPAN": masked_pan,
        },
    ]


def build_cash2card_save_extras(int_doc_number: str) -> dict[str, Any]:
    """Top-level InternetDocument.save fields required for Cash2Card COD."""
    return {
        "Number": int_doc_number,
        "Cash2Card": True,
    }


def log_cash2card_block(
    *,
    entered_pan: str,
    payout_id: str,
    backward_delivery_data: list[dict[str, Any]],
    save_payload: dict[str, Any] | None = None,
    save_response: dict[str, Any] | None = None,
) -> None:
    """Print the required Cash2Card diagnostics block."""
    masked = mask_card_number(entered_pan)
    lines = [
        "========== CASH2CARD ==========",
        f"Entered PAN: {masked}",
        f"Resolved payout id: {payout_id}",
        f"BackwardDeliveryData: {json.dumps(backward_delivery_data, ensure_ascii=False)}",
    ]
    if save_payload is not None:
        lines.append(
            "InternetDocument.save payload: "
            f"{json.dumps(save_payload, ensure_ascii=False)}",
        )
    if save_response is not None:
        lines.append(
            "InternetDocument.save response: "
            f"{json.dumps(save_response, ensure_ascii=False)}",
        )
    lines.append("================================")
    logger.info("\n".join(lines))


async def prepare_cash2card_for_ttn(
    client: NovaPoshtaClient,
    *,
    pan: str,
    sender_phone: str,
    cod_amount: str | float | int,
    telegram_user_id: int,
    db_session: AsyncSession,
    alias: str = "",
) -> Cash2CardContext:
    """Run the hidden Nova Poshta Cash2Card flow before TTN creation."""
    normalized_pan = validate_card_number(pan)
    if normalized_pan is None:
        msg = "Cash2Card requires a valid 16-digit bank card number"
        raise NovaPoshtaApiError(msg)

    normalized_phone = normalize_phone(sender_phone) or sender_phone.strip()
    if not normalized_phone:
        msg = "Cash2Card requires a valid sender phone number"
        raise NovaPoshtaApiError(msg)

    oauth = NpOAuthService(db_session)
    access_token = await oauth.get_valid_access_token(telegram_user_id)

    registration: PayoutCardRegistration = await register_payout_card(
        client,
        pan=normalized_pan,
        phone=normalized_phone,
        oauth_access_token=access_token,
    )
    int_doc_number = registration.int_doc_number

    backward_delivery_data = build_backward_delivery_data(
        cod_amount=cod_amount,
        payout_id=registration.payout_id,
        masked_pan=registration.masked_pan,
        alias=alias,
    )
    save_extras = build_cash2card_save_extras(int_doc_number)

    log_cash2card_block(
        entered_pan=normalized_pan,
        payout_id=registration.payout_id,
        backward_delivery_data=backward_delivery_data,
    )

    return Cash2CardContext(
        entered_pan=normalized_pan,
        payout_id=registration.payout_id,
        masked_pan=registration.masked_pan,
        alias=alias or "Картка",
        int_doc_number=int_doc_number,
        backward_delivery_data=backward_delivery_data,
        save_extras=save_extras,
    )


def apply_cash2card_to_wizard(
    wizard_data: dict[str, Any],
    context: Cash2CardContext,
) -> None:
    """Attach resolved Cash2Card fields to TTN wizard data."""
    wizard_data["cash2card_payout_id"] = context.payout_id
    wizard_data["cash2card_masked_pan"] = context.masked_pan
    wizard_data["cash2card_alias"] = context.alias
    wizard_data["cash2card_int_doc_number"] = context.int_doc_number
    wizard_data["cash2card_backward_delivery_data"] = context.backward_delivery_data
    wizard_data["cash2card_save_extras"] = context.save_extras
    wizard_data.pop("payment_card_ref", None)
