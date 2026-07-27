from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.constants import (
    MSG_RECIPIENT_DELETED,
    MSG_RECIPIENT_DELETE_CONFIRM,
    MSG_RECIPIENT_EDIT_CITY,
    MSG_RECIPIENT_EDIT_NAME,
    MSG_RECIPIENT_EDIT_PHONE,
    MSG_RECIPIENT_EDIT_WAREHOUSE,
    MSG_RECIPIENT_INVALID_COD,
    MSG_RECIPIENT_INVALID_PHONE,
    MSG_RECIPIENT_ASK_COD,
    MSG_RECIPIENT_UPDATED,
    MSG_RECIPIENTS_EMPTY,
    MSG_RECIPIENTS_LIST_HEADER,
    MSG_RECIPIENTS_SEARCH_EMPTY,
    MSG_RECIPIENTS_SEARCH_PROMPT,
    MSG_RECIPIENTS_TRUNCATED,
    MSG_NO_ACTIVE_NP_ACCOUNT,
    MSG_NO_ACTIVE_PAYMENT_CARD,
    MSG_TTN_ASK_PRODUCTS,
    MSG_TTN_CREATE_FAILED,
    MSG_TTN_INVALID_PRODUCTS,
    MSG_TTN_SENDER_NOT_CONFIGURED,
    RECIPIENT_SEARCH_THRESHOLD,
    CALLBACK_RECIPIENT_DELETE,
    CALLBACK_RECIPIENT_DELETE_NO,
    CALLBACK_RECIPIENT_DELETE_YES,
    CALLBACK_RECIPIENT_EDIT,
    CALLBACK_RECIPIENT_SEARCH,
    CALLBACK_RECIPIENT_TTN,
)
from app.handlers.states import RecipientWizard
from app.keyboards import (
    build_main_menu_keyboard,
    build_recipient_actions_keyboard,
    build_recipient_delete_keyboard,
    build_recipient_search_keyboard,
)
from app.models.recipient import Recipient
from app.nova_poshta import NovaPoshtaClient
from app.nova_poshta.exceptions import NovaPoshtaError
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.order_item_repository import OrderItemRepository
from app.repositories.payment_card_repository import PaymentCardRepository
from app.repositories.recipient_repository import RecipientRepository
from app.repositories.user_repository import UserRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.nova_poshta_account_service import (
    ensure_active_account_sender_cache,
    get_active_api_key,
)
from app.services.sender_cache import get_sender_cache_error
from app.services.ttn_creation_flow import process_ttn_account_selection
from app.services.ttn_service import (
    format_recipient_card,
    normalize_phone,
    parse_declared_cost,
    resolve_recipient_city_and_warehouse,
)
from app.utils.order_items import parse_product_lines

router = Router(name="recipients")


def _sender_not_configured_message(telegram_user_id: int) -> str:
    error = (
        get_sender_cache_error(telegram_user_id)
        or "Sender location is not configured"
    )
    return MSG_TTN_SENDER_NOT_CONFIGURED.format(error=error)


def _parse_recipient_id(callback_data: str, prefix: str) -> int | None:
    if not callback_data.startswith(f"{prefix}:"):
        return None
    raw_id = callback_data[len(prefix) + 1 :]
    try:
        return int(raw_id)
    except ValueError:
        return None


async def show_recipients_list(
    message: Message,
    recipient_repository: RecipientRepository,
    *,
    recipients: list[Recipient] | None = None,
) -> None:
    """Render saved recipients for the current Telegram user."""
    if message.from_user is None:
        return

    if recipients is None:
        recipients = await recipient_repository.get_all(message.from_user.id)

    if not recipients:
        await message.answer(
            MSG_RECIPIENTS_EMPTY,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    await message.answer(MSG_RECIPIENTS_LIST_HEADER)

    total = len(recipients)
    visible = recipients[:RECIPIENT_SEARCH_THRESHOLD]
    if total > RECIPIENT_SEARCH_THRESHOLD:
        await message.answer(
            MSG_RECIPIENTS_TRUNCATED.format(
                shown=RECIPIENT_SEARCH_THRESHOLD,
                total=total,
            ),
            reply_markup=build_recipient_search_keyboard(),
        )

    for recipient in visible:
        await message.answer(
            format_recipient_card(recipient),
            reply_markup=build_recipient_actions_keyboard(recipient.id),
        )


async def begin_recipients_list(
    message: Message,
    state: FSMContext,
    recipient_repository: RecipientRepository,
) -> None:
    """Open the recipient address book."""
    await state.clear()
    await show_recipients_list(message, recipient_repository)


@router.callback_query(F.data == CALLBACK_RECIPIENT_SEARCH)
async def handle_recipient_search_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.message is None:
        return

    await state.set_state(RecipientWizard.search)
    await callback.answer()
    await callback.message.answer(MSG_RECIPIENTS_SEARCH_PROMPT)


@router.message(RecipientWizard.search, F.text)
async def handle_recipient_search_query(
    message: Message,
    state: FSMContext,
    recipient_repository: RecipientRepository,
) -> None:
    if message.from_user is None or message.text is None:
        return

    if message.text == BTN_RECIPIENT_SEARCH:
        await message.answer(MSG_RECIPIENTS_SEARCH_PROMPT)
        return

    recipients = await recipient_repository.search(message.from_user.id, message.text)
    await state.clear()
    if not recipients:
        await message.answer(
            MSG_RECIPIENTS_SEARCH_EMPTY,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    await show_recipients_list(message, recipient_repository, recipients=recipients)


@router.callback_query(F.data.startswith(f"{CALLBACK_RECIPIENT_TTN}:"))
async def handle_recipient_create_ttn(
    callback: CallbackQuery,
    state: FSMContext,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    payment_card_repository: PaymentCardRepository,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        return

    active_card = await payment_card_repository.get_active_card(callback.from_user.id)
    if active_card is None:
        await callback.answer()
        await callback.message.answer(MSG_NO_ACTIVE_PAYMENT_CARD)
        return

    try:
        prepared = await ensure_active_account_sender_cache(
            nova_poshta_account_repository,
            callback.from_user.id,
        )
    except RuntimeError:
        await callback.answer()
        await callback.message.answer(
            _sender_not_configured_message(callback.from_user.id),
        )
        return

    if prepared is None:
        await callback.answer()
        await callback.message.answer(MSG_NO_ACTIVE_NP_ACCOUNT)
        return

    recipient_id = _parse_recipient_id(callback.data, CALLBACK_RECIPIENT_TTN)
    if recipient_id is None:
        await callback.answer("Некоректний одержувач", show_alert=True)
        return

    await state.clear()
    await state.set_state(RecipientWizard.ttn_cod)
    await state.update_data(recipient_id=recipient_id)
    await callback.answer()
    await callback.message.answer(MSG_RECIPIENT_ASK_COD)


@router.message(RecipientWizard.ttn_cod, F.text)
async def handle_recipient_ttn_cod(
    message: Message,
    state: FSMContext,
    recipient_repository: RecipientRepository,
) -> None:
    if message.from_user is None or message.text is None:
        return

    cod_amount = parse_declared_cost(message.text)
    if cod_amount is None:
        await message.answer(MSG_RECIPIENT_INVALID_COD)
        return

    data = await state.get_data()
    recipient_id = data.get("recipient_id")
    if recipient_id is None:
        await state.clear()
        await message.answer(
            MSG_RECIPIENTS_EMPTY,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    recipient = await recipient_repository.get_by_id(int(recipient_id), message.from_user.id)
    if recipient is None:
        await state.clear()
        await message.answer(
            MSG_RECIPIENTS_EMPTY,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    await state.update_data(cod_amount=cod_amount)
    await state.set_state(RecipientWizard.products_input)
    await message.answer(MSG_TTN_ASK_PRODUCTS)


@router.message(RecipientWizard.products_input, F.text)
async def handle_recipient_products_input(
    message: Message,
    state: FSMContext,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    recipient_repository: RecipientRepository,
    payment_card_repository: PaymentCardRepository,
    waybill_repository: WaybillRepository,
    order_item_repository: OrderItemRepository,
    user_repository: UserRepository,
) -> None:
    if message.from_user is None or message.text is None:
        return

    product_names = parse_product_lines(message.text)
    if not product_names:
        await message.answer(MSG_TTN_INVALID_PRODUCTS)
        return

    data = await state.get_data()
    recipient_id = data.get("recipient_id")
    cod_amount = data.get("cod_amount")
    if recipient_id is None or cod_amount is None:
        await state.clear()
        await message.answer(
            MSG_RECIPIENTS_EMPTY,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    recipient = await recipient_repository.get_by_id(int(recipient_id), message.from_user.id)
    if recipient is None:
        await state.clear()
        await message.answer(
            MSG_RECIPIENTS_EMPTY,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    await process_ttn_account_selection(
        message,
        state,
        source="recipient",
        product_names=product_names,
        cod_amount=str(cod_amount),
        nova_poshta_account_repository=nova_poshta_account_repository,
        waybill_repository=waybill_repository,
        user_repository=user_repository,
        recipient_repository=recipient_repository,
        payment_card_repository=payment_card_repository,
        order_item_repository=order_item_repository,
        recipient_id=int(recipient_id),
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_RECIPIENT_DELETE_YES}:"))
async def handle_recipient_delete_confirm(
    callback: CallbackQuery,
    recipient_repository: RecipientRepository,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        return

    recipient_id = _parse_recipient_id(callback.data, CALLBACK_RECIPIENT_DELETE_YES)
    if recipient_id is None:
        await callback.answer("Некоректний одержувач", show_alert=True)
        return

    deleted = await recipient_repository.delete(recipient_id, callback.from_user.id)
    await callback.answer()
    if not deleted:
        await callback.message.answer(MSG_RECIPIENTS_EMPTY)
        return

    await callback.message.answer(
        MSG_RECIPIENT_DELETED,
        reply_markup=build_main_menu_keyboard(),
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_RECIPIENT_DELETE_NO}:"))
async def handle_recipient_delete_cancel(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await callback.message.answer(
        "Скасовано.",
        reply_markup=build_main_menu_keyboard(),
    )


@router.callback_query(
    F.data.startswith(f"{CALLBACK_RECIPIENT_DELETE}:")
    & ~F.data.startswith(f"{CALLBACK_RECIPIENT_DELETE_YES}:")
    & ~F.data.startswith(f"{CALLBACK_RECIPIENT_DELETE_NO}:"),
)
async def handle_recipient_delete_prompt(callback: CallbackQuery) -> None:
    if callback.data is None or callback.message is None:
        return

    recipient_id = _parse_recipient_id(callback.data, CALLBACK_RECIPIENT_DELETE)
    if recipient_id is None:
        await callback.answer("Некоректний одержувач", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        MSG_RECIPIENT_DELETE_CONFIRM,
        reply_markup=build_recipient_delete_keyboard(recipient_id),
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_RECIPIENT_EDIT}:"))
async def handle_recipient_edit_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.data is None or callback.message is None:
        return

    recipient_id = _parse_recipient_id(callback.data, CALLBACK_RECIPIENT_EDIT)
    if recipient_id is None:
        await callback.answer("Некоректний одержувач", show_alert=True)
        return

    await state.clear()
    await state.set_state(RecipientWizard.edit_name)
    await state.update_data(recipient_id=recipient_id)
    await callback.answer()
    await callback.message.answer(MSG_RECIPIENT_EDIT_NAME)


@router.message(RecipientWizard.edit_name, F.text)
async def handle_recipient_edit_name(message: Message, state: FSMContext) -> None:
    if message.text is None or not message.text.strip():
        await message.answer(MSG_RECIPIENT_EDIT_NAME)
        return

    await state.update_data(full_name=message.text.strip())
    await state.set_state(RecipientWizard.edit_phone)
    await message.answer(MSG_RECIPIENT_EDIT_PHONE)


@router.message(RecipientWizard.edit_phone, F.text)
async def handle_recipient_edit_phone(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return

    phone = normalize_phone(message.text)
    if phone is None:
        await message.answer(MSG_RECIPIENT_INVALID_PHONE)
        return

    await state.update_data(phone=phone)
    await state.set_state(RecipientWizard.edit_city)
    await message.answer(MSG_RECIPIENT_EDIT_CITY)


@router.message(RecipientWizard.edit_city, F.text)
async def handle_recipient_edit_city(message: Message, state: FSMContext) -> None:
    if message.text is None or not message.text.strip():
        await message.answer(MSG_RECIPIENT_EDIT_CITY)
        return

    await state.update_data(city_query=message.text.strip())
    await state.set_state(RecipientWizard.edit_warehouse)
    await message.answer(MSG_RECIPIENT_EDIT_WAREHOUSE)


@router.message(RecipientWizard.edit_warehouse, F.text)
async def handle_recipient_edit_warehouse(
    message: Message,
    state: FSMContext,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    recipient_repository: RecipientRepository,
) -> None:
    if message.from_user is None or message.text is None or not message.text.strip():
        await message.answer(MSG_RECIPIENT_EDIT_WAREHOUSE)
        return

    data = await state.get_data()
    recipient_id = data.get("recipient_id")
    if recipient_id is None:
        await state.clear()
        await message.answer(MSG_RECIPIENTS_EMPTY, reply_markup=build_main_menu_keyboard())
        return

    existing = await recipient_repository.get_by_id(int(recipient_id), message.from_user.id)
    if existing is None:
        await state.clear()
        await message.answer(MSG_RECIPIENTS_EMPTY, reply_markup=build_main_menu_keyboard())
        return

    api_key = await get_active_api_key(nova_poshta_account_repository, message.from_user.id)
    if api_key is None:
        await state.clear()
        await message.answer(
            MSG_NO_ACTIVE_NP_ACCOUNT,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    city_query = str(data.get("city_query") or existing.city_name)
    warehouse_number = message.text.strip().lstrip("№")

    try:
        async with NovaPoshtaClient(api_key) as client:
            recipient_city, recipient_warehouse = await resolve_recipient_city_and_warehouse(
                client,
                city_query=city_query,
                warehouse_number=warehouse_number,
            )
    except NovaPoshtaError as exc:
        await message.answer(MSG_TTN_CREATE_FAILED.format(error=str(exc)))
        return

    updated = await recipient_repository.save_recipient(
        telegram_user_id=message.from_user.id,
        full_name=str(data.get("full_name") or existing.full_name),
        phone=str(data.get("phone") or existing.phone),
        city_name=recipient_city["name"],
        city_ref=recipient_city["delivery_city"],
        warehouse_number=recipient_warehouse["number"],
        warehouse_ref=recipient_warehouse["ref"],
    )

    await state.clear()
    await message.answer(MSG_RECIPIENT_UPDATED)
    await message.answer(
        format_recipient_card(updated),
        reply_markup=build_recipient_actions_keyboard(updated.id),
    )
