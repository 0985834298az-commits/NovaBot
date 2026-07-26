from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from app.constants import (
    ASK_API_KEY_MESSAGE,
    BTN_CREATE_TTN,
    CALLBACK_TTN_CITY,
    CALLBACK_TTN_EDIT_FIELD,
    CALLBACK_TTN_REVIEW_CANCEL,
    CALLBACK_TTN_REVIEW_CREATE,
    CALLBACK_TTN_REVIEW_EDIT,
    CALLBACK_TTN_WAREHOUSE,
    MSG_TTN_ASK_CARGO_DESCRIPTION,
    MSG_TTN_ASK_DECLARED_COST,
    MSG_TTN_ASK_RECIPIENT_CITY,
    MSG_TTN_ASK_RECIPIENT_NAME,
    MSG_TTN_ASK_RECIPIENT_PHONE,
    MSG_TTN_ASK_RECIPIENT_WAREHOUSE,
    MSG_TTN_ASK_SENDER_CITY,
    MSG_TTN_ASK_SENDER_WAREHOUSE,
    MSG_TTN_ASK_WEIGHT,
    MSG_TTN_CANCELLED,
    MSG_TTN_CREATE_FAILED,
    MSG_TTN_CREATED,
    MSG_TTN_EDIT_PROMPT,
    MSG_TTN_INVALID_COST,
    MSG_TTN_INVALID_PHONE,
    MSG_TTN_INVALID_WEIGHT,
    MSG_TTN_NEED_API_KEY,
    MSG_TTN_NO_CITIES,
    MSG_TTN_NO_WAREHOUSES,
    MSG_TTN_PRINT_LINK,
)
from app.handlers.states import TtnWizard, WaitingForApiKey
from app.keyboards import (
    build_city_keyboard,
    build_edit_fields_keyboard,
    build_main_menu_keyboard,
    build_review_keyboard,
    build_warehouse_keyboard,
)
from app.nova_poshta import NovaPoshtaClient
from app.nova_poshta.exceptions import NovaPoshtaError
from app.repositories.user_repository import UserRepository
from app.services.ttn_service import (
    build_print_link,
    build_save_properties,
    fetch_sender_profile,
    format_review_text,
    normalize_phone,
    parse_declared_cost,
    parse_settlements,
    parse_warehouses,
    parse_weight,
)

router = Router(name="ttn")

VALID_TTN_SIDES = frozenset({"sender", "recipient"})

FIELD_PROMPTS: dict[str, str] = {
    "sender_city": MSG_TTN_ASK_SENDER_CITY,
    "sender_warehouse": MSG_TTN_ASK_SENDER_WAREHOUSE,
    "recipient_name": MSG_TTN_ASK_RECIPIENT_NAME,
    "recipient_phone": MSG_TTN_ASK_RECIPIENT_PHONE,
    "recipient_city": MSG_TTN_ASK_RECIPIENT_CITY,
    "recipient_warehouse": MSG_TTN_ASK_RECIPIENT_WAREHOUSE,
    "cargo_description": MSG_TTN_ASK_CARGO_DESCRIPTION,
    "weight": MSG_TTN_ASK_WEIGHT,
    "declared_cost": MSG_TTN_ASK_DECLARED_COST,
}

FIELD_STATES = {
    "sender_city": TtnWizard.sender_city,
    "sender_warehouse": TtnWizard.sender_warehouse,
    "recipient_name": TtnWizard.recipient_name,
    "recipient_phone": TtnWizard.recipient_phone,
    "recipient_city": TtnWizard.recipient_city,
    "recipient_warehouse": TtnWizard.recipient_warehouse,
    "cargo_description": TtnWizard.cargo_description,
    "weight": TtnWizard.weight,
    "declared_cost": TtnWizard.declared_cost,
}


def _parse_city_callback(callback_data: str) -> tuple[str, str] | None:
    """Parse city callback data: ttn:city:{side}:{ref}."""
    prefix = f"{CALLBACK_TTN_CITY}:"
    if not callback_data.startswith(prefix):
        return None

    payload = callback_data[len(prefix):]
    side, _, city_ref = payload.partition(":")
    if side not in VALID_TTN_SIDES or not city_ref:
        return None

    return side, city_ref


def _find_city_option(
    options: list[dict[str, str]],
    city_ref: str,
) -> dict[str, str] | None:
    """Find a settlement option by its Ref."""
    for item in options:
        if item.get("ref") == city_ref:
            return item
    return None


async def _get_api_key(
    user_repository: UserRepository,
    telegram_id: int,
) -> str | None:
    user = await user_repository.get_user(telegram_id)
    if user is None or not user.api_key:
        return None
    return user.api_key


async def _show_review(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(TtnWizard.review)
    await message.answer(
        format_review_text(data),
        reply_markup=build_review_keyboard(),
    )


async def _continue_after_edit(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("edit_mode"):
        await state.update_data(edit_mode=False)
        await _show_review(message, state)
        return

    current_state = await state.get_state()
    transitions = {
        TtnWizard.sender_city.state: (
            TtnWizard.sender_warehouse,
            MSG_TTN_ASK_SENDER_WAREHOUSE,
        ),
        TtnWizard.sender_warehouse.state: (
            TtnWizard.recipient_name,
            MSG_TTN_ASK_RECIPIENT_NAME,
        ),
        TtnWizard.recipient_name.state: (
            TtnWizard.recipient_phone,
            MSG_TTN_ASK_RECIPIENT_PHONE,
        ),
        TtnWizard.recipient_phone.state: (
            TtnWizard.recipient_city,
            MSG_TTN_ASK_RECIPIENT_CITY,
        ),
        TtnWizard.recipient_city.state: (
            TtnWizard.recipient_warehouse,
            MSG_TTN_ASK_RECIPIENT_WAREHOUSE,
        ),
        TtnWizard.recipient_warehouse.state: (
            TtnWizard.cargo_description,
            MSG_TTN_ASK_CARGO_DESCRIPTION,
        ),
        TtnWizard.cargo_description.state: (
            TtnWizard.weight,
            MSG_TTN_ASK_WEIGHT,
        ),
        TtnWizard.weight.state: (
            TtnWizard.declared_cost,
            MSG_TTN_ASK_DECLARED_COST,
        ),
        TtnWizard.declared_cost.state: (None, None),
    }
    next_step = transitions.get(current_state)
    if next_step is None:
        await _show_review(message, state)
        return

    next_state, prompt = next_step
    await state.set_state(next_state)
    await message.answer(prompt)


async def _search_cities(
    message: Message,
    state: FSMContext,
    *,
    side: str,
    query: str,
    user_repository: UserRepository,
) -> None:
    if message.from_user is None:
        return

    api_key = await _get_api_key(user_repository, message.from_user.id)
    if api_key is None:
        await state.clear()
        await message.answer(MSG_TTN_NEED_API_KEY)
        return

    async with NovaPoshtaClient(api_key) as client:
        response = await client.search_settlements(query)

    settlements = parse_settlements(response)
    if not settlements:
        await message.answer(MSG_TTN_NO_CITIES)
        return

    await state.update_data(**{f"{side}_city_options": settlements})
    await message.answer(
        "Оберіть населений пункт:",
        reply_markup=build_city_keyboard(settlements, side=side),
    )


async def _search_warehouses(
    message: Message,
    state: FSMContext,
    *,
    side: str,
    query: str,
    user_repository: UserRepository,
) -> None:
    if message.from_user is None:
        return

    data = await state.get_data()
    city = data.get(f"{side}_city")
    if not city:
        await message.answer(MSG_TTN_NO_WAREHOUSES)
        return

    api_key = await _get_api_key(user_repository, message.from_user.id)
    if api_key is None:
        await state.clear()
        await message.answer(MSG_TTN_NEED_API_KEY)
        return

    async with NovaPoshtaClient(api_key) as client:
        response = await client.get_warehouses(
            city["delivery_city"],
            find_by_string=query,
        )

    warehouses = parse_warehouses(response)
    if not warehouses:
        await message.answer(MSG_TTN_NO_WAREHOUSES)
        return

    await state.update_data(**{f"{side}_warehouse_options": warehouses})
    await message.answer(
        "Оберіть відділення:",
        reply_markup=build_warehouse_keyboard(warehouses, side=side),
    )


@router.message(F.text == BTN_CREATE_TTN, StateFilter(None))
async def start_ttn_wizard(
    message: Message,
    state: FSMContext,
    user_repository: UserRepository,
) -> None:
    """Start TTN creation wizard."""
    if message.from_user is None:
        return

    user = await user_repository.get_user(message.from_user.id)
    if user is None or not user.api_key:
        await state.set_state(WaitingForApiKey.api_key)
        await message.answer(ASK_API_KEY_MESSAGE)
        return

    await state.clear()
    await state.set_state(TtnWizard.sender_city)
    await message.answer(MSG_TTN_ASK_SENDER_CITY)


@router.message(TtnWizard.sender_city, F.text)
@router.message(TtnWizard.recipient_city, F.text)
async def handle_city_query(
    message: Message,
    state: FSMContext,
    user_repository: UserRepository,
) -> None:
    """Search cities while the user types."""
    if message.text is None:
        return

    query = message.text.strip()
    if len(query) < 2:
        await message.answer(MSG_TTN_NO_CITIES)
        return

    current_state = await state.get_state()
    side = "sender" if current_state == TtnWizard.sender_city.state else "recipient"
    await _search_cities(
        message,
        state,
        side=side,
        query=query,
        user_repository=user_repository,
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_TTN_CITY}:"))
async def handle_city_select(callback: CallbackQuery, state: FSMContext) -> None:
    """Save selected city and move to the next step."""
    if callback.data is None or callback.message is None:
        return

    parsed = _parse_city_callback(callback.data)
    if parsed is None:
        await callback.answer("Некоректний вибір", show_alert=True)
        return

    side, city_ref = parsed
    data = await state.get_data()
    options: list[dict[str, str]] = data.get(f"{side}_city_options", [])
    selected = _find_city_option(options, city_ref)
    if selected is None:
        await callback.answer("Некоректний вибір", show_alert=True)
        return

    await state.update_data(**{f"{side}_city": selected})
    await callback.answer()

    if data.get("edit_mode"):
        await state.set_state(
            TtnWizard.sender_warehouse if side == "sender" else TtnWizard.recipient_warehouse,
        )
        prompt = (
            MSG_TTN_ASK_SENDER_WAREHOUSE
            if side == "sender"
            else MSG_TTN_ASK_RECIPIENT_WAREHOUSE
        )
        await callback.message.answer(prompt)
        return

    if side == "sender":
        await state.set_state(TtnWizard.sender_warehouse)
        await callback.message.answer(MSG_TTN_ASK_SENDER_WAREHOUSE)
        return

    await state.set_state(TtnWizard.recipient_warehouse)
    await callback.message.answer(MSG_TTN_ASK_RECIPIENT_WAREHOUSE)


@router.message(TtnWizard.sender_warehouse, F.text)
@router.message(TtnWizard.recipient_warehouse, F.text)
async def handle_warehouse_query(
    message: Message,
    state: FSMContext,
    user_repository: UserRepository,
) -> None:
    """Search warehouses for the selected city."""
    if message.text is None:
        return

    current_state = await state.get_state()
    side = "sender" if current_state == TtnWizard.sender_warehouse.state else "recipient"
    await _search_warehouses(
        message,
        state,
        side=side,
        query=message.text.strip(),
        user_repository=user_repository,
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_TTN_WAREHOUSE}:"))
async def handle_warehouse_select(callback: CallbackQuery, state: FSMContext) -> None:
    """Save selected warehouse and continue the wizard."""
    if callback.data is None or callback.message is None:
        return

    _, side, index_raw = callback.data.split(":", maxsplit=2)
    data = await state.get_data()
    options: list[dict[str, str]] = data.get(f"{side}_warehouse_options", [])
    try:
        selected = options[int(index_raw)]
    except (ValueError, IndexError):
        await callback.answer("Некоректний вибір", show_alert=True)
        return

    await state.update_data(**{f"{side}_warehouse": selected})
    await callback.answer()

    if data.get("edit_mode"):
        await state.update_data(edit_mode=False)
        await _show_review(callback.message, state)
        return

    if side == "sender":
        await state.set_state(TtnWizard.recipient_name)
        await callback.message.answer(MSG_TTN_ASK_RECIPIENT_NAME)
        return

    await state.set_state(TtnWizard.cargo_description)
    await callback.message.answer(MSG_TTN_ASK_CARGO_DESCRIPTION)


@router.message(TtnWizard.recipient_name, F.text)
async def handle_recipient_name(message: Message, state: FSMContext) -> None:
    if message.text is None or not message.text.strip():
        await message.answer(MSG_TTN_ASK_RECIPIENT_NAME)
        return

    await state.update_data(recipient_name=message.text.strip())
    await _continue_after_edit(message, state)


@router.message(TtnWizard.recipient_phone, F.text)
async def handle_recipient_phone(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return

    phone = normalize_phone(message.text)
    if phone is None:
        await message.answer(MSG_TTN_INVALID_PHONE)
        return

    await state.update_data(recipient_phone=phone)
    await _continue_after_edit(message, state)


@router.message(TtnWizard.cargo_description, F.text)
async def handle_cargo_description(message: Message, state: FSMContext) -> None:
    if message.text is None or not message.text.strip():
        await message.answer(MSG_TTN_ASK_CARGO_DESCRIPTION)
        return

    await state.update_data(cargo_description=message.text.strip())
    await _continue_after_edit(message, state)


@router.message(TtnWizard.weight, F.text)
async def handle_weight(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return

    weight = parse_weight(message.text)
    if weight is None:
        await message.answer(MSG_TTN_INVALID_WEIGHT)
        return

    await state.update_data(weight=weight)
    await _continue_after_edit(message, state)


@router.message(TtnWizard.declared_cost, F.text)
async def handle_declared_cost(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return

    declared_cost = parse_declared_cost(message.text)
    if declared_cost is None:
        await message.answer(MSG_TTN_INVALID_COST)
        return

    await state.update_data(declared_cost=declared_cost)
    await _continue_after_edit(message, state)


@router.callback_query(F.data == CALLBACK_TTN_REVIEW_EDIT)
async def handle_review_edit(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await callback.message.answer(
        MSG_TTN_EDIT_PROMPT,
        reply_markup=build_edit_fields_keyboard(),
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_TTN_EDIT_FIELD}:"))
async def handle_edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None:
        return

    field_key = callback.data.split(":", maxsplit=1)[1]
    if field_key not in FIELD_PROMPTS:
        await callback.answer("Невідоме поле", show_alert=True)
        return

    await state.update_data(edit_mode=True)
    await state.set_state(FIELD_STATES[field_key])
    await callback.answer()
    await callback.message.answer(FIELD_PROMPTS[field_key])


@router.callback_query(F.data == CALLBACK_TTN_REVIEW_CANCEL)
async def handle_review_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await state.clear()
    await callback.answer()
    await callback.message.answer(
        MSG_TTN_CANCELLED,
        reply_markup=build_main_menu_keyboard(),
    )


@router.callback_query(F.data == CALLBACK_TTN_REVIEW_CREATE)
async def handle_review_create(
    callback: CallbackQuery,
    state: FSMContext,
    user_repository: UserRepository,
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    api_key = await _get_api_key(user_repository, callback.from_user.id)
    if api_key is None:
        await callback.answer(MSG_TTN_NEED_API_KEY, show_alert=True)
        return

    data = await state.get_data()
    await callback.answer("Створюємо ТТН...")

    try:
        async with NovaPoshtaClient(api_key) as client:
            sender_profile = await fetch_sender_profile(client)
            save_properties = build_save_properties(data, sender_profile)
            response = await client.save_internet_document(save_properties)
    except NovaPoshtaError as exc:
        logger.error("TTN creation failed: {}", exc)
        await callback.message.answer(
            MSG_TTN_CREATE_FAILED.format(error=str(exc)),
            reply_markup=build_main_menu_keyboard(),
        )
        return

    document = (response.get("data") or [{}])[0]
    ttn_number = str(document.get("IntDocNumber") or "—")
    reference = str(document.get("Ref") or "—")
    await state.clear()

    await callback.message.answer(
        MSG_TTN_CREATED.format(ttn_number=ttn_number, reference=reference),
        reply_markup=build_main_menu_keyboard(),
    )

    if reference != "—":
        print_link = build_print_link(reference, api_key)
        await callback.message.answer(MSG_TTN_PRINT_LINK.format(link=print_link))
