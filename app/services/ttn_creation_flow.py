from __future__ import annotations

from typing import Any, Literal

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger

from app.constants import (
    MSG_ACCOUNT_AUTO_SWITCHED,
    MSG_ACCOUNT_LIMIT_EXCEEDED,
    MSG_ACCOUNT_LIMIT_WARNING,
    MSG_ACCOUNT_SELECT_HEADER,
    MSG_ACCOUNT_SELECTED_ACTIVE,
    MSG_NO_ACTIVE_NP_ACCOUNT,
    MSG_NO_ACTIVE_PAYMENT_CARD,
    MSG_TTN_CREATE_FAILED,
    MSG_TTN_CREATING,
    MSG_TTN_PRINT_LINK,
    MSG_TTN_SENDER_NOT_CONFIGURED,
)
from app.handlers.states import RecipientWizard, TtnWizard
from app.keyboards import (
    build_account_limit_keyboard,
    build_account_pick_keyboard,
    build_main_menu_keyboard,
)
from app.nova_poshta import NovaPoshtaClient
from app.nova_poshta.exceptions import NovaPoshtaError
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.order_item_repository import OrderItemRepository
from app.repositories.payment_card_repository import PaymentCardRepository
from app.repositories.recipient_repository import RecipientRepository
from app.repositories.user_repository import UserRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.account_selection_service import (
    AccountSelectionOutcome,
    SelectionAction,
    activate_account_for_user,
    build_account_usages,
    cod_amount_from_string,
    format_account_usage_block,
    format_available_accounts,
    resolve_account_for_cod,
)
from app.services.nova_poshta_account_service import ensure_active_account_sender_cache
from app.services.order_service import create_ttn_with_order_items
from app.services.payment_card_service import (
    apply_active_card_to_wizard,
    is_active_card_ready,
)
from app.services.sender_cache import get_sender_cache_error
from app.services.waybill_sync_service import sync_user_waybills
from app.services.ttn_service import (
    TtnOrderInput,
    build_print_link,
    build_wizard_data_from_saved_recipient,
    fetch_sender_profile,
    format_ttn_success_message,
    prepare_wizard_data_from_order,
)
from app.utils.money import format_money_uah

PendingTtnSource = Literal["ttn", "recipient"]
PENDING_TTN_KEY = "pending_ttn"


def _sender_not_configured_message(telegram_user_id: int) -> str:
    error = (
        get_sender_cache_error(telegram_user_id)
        or "Sender location is not configured"
    )
    return MSG_TTN_SENDER_NOT_CONFIGURED.format(error=error)


def _limit_message(outcome: AccountSelectionOutcome) -> str:
    available = format_available_accounts(list(outcome.usages))
    required = format_money_uah(outcome.cod_amount)
    if outcome.action is SelectionAction.WARN_EXCEED:
        return MSG_ACCOUNT_LIMIT_WARNING.format(
            required=required,
            available=available,
        )
    return MSG_ACCOUNT_LIMIT_EXCEEDED.format(
        required=required,
        available=available,
    )


async def store_pending_ttn(
    state: FSMContext,
    *,
    source: PendingTtnSource,
    product_names: list[str],
    cod_amount: str,
    recipient_name: str | None = None,
    recipient_phone: str | None = None,
    city_query: str | None = None,
    warehouse_number: str | None = None,
    recipient_id: int | None = None,
) -> None:
    """Persist TTN payload while waiting for account selection."""
    pending: dict[str, Any] = {
        "source": source,
        "product_names": product_names,
        "cod_amount": cod_amount,
    }
    if source == "ttn":
        pending.update(
            {
                "recipient_name": recipient_name,
                "recipient_phone": recipient_phone,
                "city_query": city_query,
                "warehouse_number": warehouse_number,
            },
        )
    else:
        pending["recipient_id"] = recipient_id

    await state.update_data(**{PENDING_TTN_KEY: pending})
    if source == "ttn":
        await state.set_state(TtnWizard.account_choice)
    else:
        await state.set_state(RecipientWizard.account_choice)


async def get_pending_ttn(state: FSMContext) -> dict[str, Any] | None:
    data = await state.get_data()
    pending = data.get(PENDING_TTN_KEY)
    if not isinstance(pending, dict):
        return None
    return pending


async def clear_pending_ttn(state: FSMContext) -> None:
    await state.update_data(**{PENDING_TTN_KEY: None})


async def notify_auto_switch(
    message: Message,
    outcome: AccountSelectionOutcome,
) -> None:
    if outcome.previous_account is None:
        return
    await message.answer(
        MSG_ACCOUNT_AUTO_SWITCHED.format(
            previous_name=outcome.previous_account.account_name,
            current_name=outcome.selected_account.account_name,
        ),
    )


async def prompt_account_choice(
    message: Message,
    state: FSMContext,
    outcome: AccountSelectionOutcome,
    *,
    source: PendingTtnSource,
    product_names: list[str],
    cod_amount: str,
    recipient_name: str | None = None,
    recipient_phone: str | None = None,
    city_query: str | None = None,
    warehouse_number: str | None = None,
    recipient_id: int | None = None,
) -> None:
    await store_pending_ttn(
        state,
        source=source,
        product_names=product_names,
        cod_amount=cod_amount,
        recipient_name=recipient_name,
        recipient_phone=recipient_phone,
        city_query=city_query,
        warehouse_number=warehouse_number,
        recipient_id=recipient_id,
    )
    await message.answer(
        _limit_message(outcome),
        reply_markup=build_account_limit_keyboard(),
    )


async def show_manual_account_selection(
    message: Message,
    account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
    telegram_user_id: int,
) -> None:
    usages = await build_account_usages(
        account_repository,
        waybill_repository,
        telegram_user_id,
    )
    if not usages:
        await message.answer(MSG_NO_ACTIVE_NP_ACCOUNT)
        return

    lines = [MSG_ACCOUNT_SELECT_HEADER, ""]
    lines.extend(format_account_usage_block(usage) for usage in usages)
    await message.answer(
        "\n\n".join(lines),
        reply_markup=build_account_pick_keyboard(usages),
    )


async def _create_ttn_from_pending(
    message: Message,
    pending: dict[str, Any],
    *,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    recipient_repository: RecipientRepository,
    payment_card_repository: PaymentCardRepository,
    waybill_repository: WaybillRepository,
    order_item_repository: OrderItemRepository,
    selected_account_id: int,
) -> bool:
    if message.from_user is None:
        return False

    product_names = list(pending.get("product_names") or [])
    cod_amount = str(pending.get("cod_amount") or "0")
    source = pending.get("source")

    active_card = await payment_card_repository.get_active_card(message.from_user.id)
    if not is_active_card_ready(active_card):
        await message.answer(
            MSG_NO_ACTIVE_PAYMENT_CARD,
            reply_markup=build_main_menu_keyboard(),
        )
        return False

    assert active_card is not None

    try:
        prepared = await ensure_active_account_sender_cache(
            nova_poshta_account_repository,
            message.from_user.id,
        )
    except RuntimeError:
        await message.answer(
            _sender_not_configured_message(message.from_user.id),
            reply_markup=build_main_menu_keyboard(),
        )
        return False

    if prepared is None:
        await message.answer(
            MSG_NO_ACTIVE_NP_ACCOUNT,
            reply_markup=build_main_menu_keyboard(),
        )
        return False

    api_key, sender_location = prepared
    await message.answer(MSG_TTN_CREATING)

    try:
        if source == "ttn":
            order = TtnOrderInput(
                recipient_name=str(pending.get("recipient_name") or ""),
                recipient_phone=str(pending.get("recipient_phone") or ""),
                city_query=str(pending.get("city_query") or ""),
                warehouse_number=str(pending.get("warehouse_number") or ""),
                cod_amount=cod_amount,
            )
            async with NovaPoshtaClient(api_key) as client:
                wizard_data, sender_profile = await prepare_wizard_data_from_order(
                    client,
                    order,
                    sender_location,
                )
            save_recipient = True
        else:
            recipient_id = pending.get("recipient_id")
            if recipient_id is None:
                raise NovaPoshtaError("Recipient was not found for TTN creation")
            recipient = await recipient_repository.get_by_id(
                int(recipient_id),
                message.from_user.id,
            )
            if recipient is None:
                raise NovaPoshtaError("Recipient was not found for TTN creation")
            wizard_data = build_wizard_data_from_saved_recipient(
                recipient,
                cod_amount,
                sender_location,
            )
            async with NovaPoshtaClient(api_key) as client:
                sender_profile = await fetch_sender_profile(client)
            save_recipient = False

        apply_active_card_to_wizard(wizard_data, active_card)
        document, _waybill = await create_ttn_with_order_items(
            telegram_user_id=message.from_user.id,
            wizard_data=wizard_data,
            sender_profile=sender_profile,
            product_names=product_names,
            api_key=api_key,
            nova_poshta_account_id=selected_account_id,
            recipient_repository=recipient_repository,
            waybill_repository=waybill_repository,
            order_item_repository=order_item_repository,
            save_recipient=save_recipient,
        )
    except NovaPoshtaError as exc:
        logger.error("TTN creation failed for user {}: {}", message.from_user.id, exc)
        await message.answer(MSG_TTN_CREATE_FAILED.format(error=str(exc)))
        return False

    ttn_number = str(document.get("IntDocNumber") or "—")
    reference = str(document.get("Ref") or "")
    delivery_cost = document.get("CostOnSite") or document.get("DocumentCost")

    await message.answer(
        format_ttn_success_message(
            ttn_number=ttn_number,
            delivery_cost=delivery_cost,
        ),
        reply_markup=build_main_menu_keyboard(),
    )

    if reference:
        print_link = build_print_link(reference, api_key)
        await message.answer(MSG_TTN_PRINT_LINK.format(link=print_link))

    try:
        await sync_user_waybills(
            telegram_user_id=message.from_user.id,
            account_repository=nova_poshta_account_repository,
            waybill_repository=waybill_repository,
        )
    except Exception as exc:
        logger.exception(
            "Automatic waybill sync failed after TTN creation for user {}: {}",
            message.from_user.id,
            exc,
        )
    return True


async def execute_pending_ttn_creation(
    message: Message,
    state: FSMContext,
    *,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    recipient_repository: RecipientRepository,
    payment_card_repository: PaymentCardRepository,
    waybill_repository: WaybillRepository,
    order_item_repository: OrderItemRepository,
    user_repository: UserRepository,
    account_id: int | None = None,
    force_current: bool = False,
) -> bool:
    """Create a TTN from pending FSM data."""
    if message.from_user is None:
        return False

    pending = await get_pending_ttn(state)
    if pending is None:
        await state.clear()
        await message.answer(
            "Сесію створення ТТН не знайдено.",
            reply_markup=build_main_menu_keyboard(),
        )
        return False

    cod_amount = str(pending.get("cod_amount") or "0")

    if account_id is not None:
        activated = await activate_account_for_user(
            account_repository=nova_poshta_account_repository,
            telegram_user_id=message.from_user.id,
            account_id=account_id,
        )
        if activated is None:
            await message.answer(MSG_NO_ACTIVE_NP_ACCOUNT)
            return False
        await message.answer(
            MSG_ACCOUNT_SELECTED_ACTIVE.format(account_name=activated.account_name),
        )

    outcome = await resolve_account_for_cod(
        account_repository=nova_poshta_account_repository,
        waybill_repository=waybill_repository,
        user_repository=user_repository,
        telegram_user_id=message.from_user.id,
        cod_amount=cod_amount_from_string(cod_amount),
        force_current=force_current,
    )
    if outcome is None:
        await state.clear()
        await message.answer(
            MSG_NO_ACTIVE_NP_ACCOUNT,
            reply_markup=build_main_menu_keyboard(),
        )
        return False

    if outcome.requires_user_choice and not force_current:
        await prompt_account_choice(
            message,
            state,
            outcome,
            source=pending["source"],
            product_names=list(pending.get("product_names") or []),
            cod_amount=cod_amount,
            recipient_name=pending.get("recipient_name"),
            recipient_phone=pending.get("recipient_phone"),
            city_query=pending.get("city_query"),
            warehouse_number=pending.get("warehouse_number"),
            recipient_id=pending.get("recipient_id"),
        )
        return False

    if outcome.action is SelectionAction.AUTO_SWITCHED:
        await notify_auto_switch(message, outcome)

    created = await _create_ttn_from_pending(
        message,
        pending,
        nova_poshta_account_repository=nova_poshta_account_repository,
        recipient_repository=recipient_repository,
        payment_card_repository=payment_card_repository,
        waybill_repository=waybill_repository,
        order_item_repository=order_item_repository,
        selected_account_id=outcome.selected_account.id,
    )
    if created:
        await clear_pending_ttn(state)
        await state.clear()
    return created


async def process_ttn_account_selection(
    message: Message,
    state: FSMContext,
    *,
    source: PendingTtnSource,
    product_names: list[str],
    cod_amount: str,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
    user_repository: UserRepository,
    recipient_repository: RecipientRepository,
    payment_card_repository: PaymentCardRepository,
    order_item_repository: OrderItemRepository,
    recipient_name: str | None = None,
    recipient_phone: str | None = None,
    city_query: str | None = None,
    warehouse_number: str | None = None,
    recipient_id: int | None = None,
) -> None:
    """Resolve account limits and either create TTN or ask the user to choose."""
    if message.from_user is None:
        return

    active_card = await payment_card_repository.get_active_card(message.from_user.id)
    if not is_active_card_ready(active_card):
        await state.clear()
        await message.answer(
            MSG_NO_ACTIVE_PAYMENT_CARD,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    outcome = await resolve_account_for_cod(
        account_repository=nova_poshta_account_repository,
        waybill_repository=waybill_repository,
        user_repository=user_repository,
        telegram_user_id=message.from_user.id,
        cod_amount=cod_amount_from_string(cod_amount),
    )
    if outcome is None:
        await state.clear()
        await message.answer(
            MSG_NO_ACTIVE_NP_ACCOUNT,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    if outcome.requires_user_choice:
        await prompt_account_choice(
            message,
            state,
            outcome,
            source=source,
            product_names=product_names,
            cod_amount=cod_amount,
            recipient_name=recipient_name,
            recipient_phone=recipient_phone,
            city_query=city_query,
            warehouse_number=warehouse_number,
            recipient_id=recipient_id,
        )
        return

    if outcome.action is SelectionAction.AUTO_SWITCHED:
        await notify_auto_switch(message, outcome)

    pending: dict[str, Any] = {
        "source": source,
        "product_names": product_names,
        "cod_amount": cod_amount,
    }
    if source == "ttn":
        pending.update(
            {
                "recipient_name": recipient_name,
                "recipient_phone": recipient_phone,
                "city_query": city_query,
                "warehouse_number": warehouse_number,
            },
        )
    else:
        pending["recipient_id"] = recipient_id

    created = await _create_ttn_from_pending(
        message,
        pending,
        nova_poshta_account_repository=nova_poshta_account_repository,
        recipient_repository=recipient_repository,
        payment_card_repository=payment_card_repository,
        waybill_repository=waybill_repository,
        order_item_repository=order_item_repository,
        selected_account_id=outcome.selected_account.id,
    )
    if created:
        await state.clear()
