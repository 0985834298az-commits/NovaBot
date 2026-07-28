from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.constants import (
    MSG_ACTION_CANCELLED,
    MSG_CARD_ACTIVE_CHANGED,
    MSG_CARD_ASK_NAME,
    MSG_CARD_ASK_NUMBER,
    MSG_CARD_ASK_OWNER,
    MSG_CARD_DELETE_CONFIRM,
    MSG_CARD_DELETED,
    MSG_CARD_EDIT_NAME,
    MSG_CARD_EDIT_NUMBER,
    MSG_CARD_EDIT_OWNER,
    MSG_CARD_INVALID_NUMBER,
    MSG_CARD_SAVED,
    MSG_CARD_UPDATED,
    MSG_CARDS_EMPTY,
    MSG_CARDS_FOOTER,
    MSG_CARDS_LIST_HEADER,
    MSG_MAIN_MENU,
    MSG_NO_ACTIVE_NP_ACCOUNT,
    CALLBACK_CARD_ADD,
    CALLBACK_CARD_BACK,
    CALLBACK_CARD_DELETE,
    CALLBACK_CARD_DELETE_NO,
    CALLBACK_CARD_DELETE_YES,
    CALLBACK_CARD_EDIT,
    CALLBACK_CARD_SELECT,
)
from app.handlers.states import PaymentCardWizard
from app.keyboards import (
    build_main_menu_keyboard,
    build_payment_card_actions_keyboard,
    build_payment_card_delete_keyboard,
    build_payment_cards_footer_keyboard,
)
from app.models.nova_poshta_account import NovaPoshtaAccount
from app.models.payment_card import PaymentCard
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.payment_card_repository import PaymentCardRepository
from app.utils.payment_card import format_payment_card, validate_card_number

router = Router(name="payment_cards")


def _parse_card_id(callback_data: str, prefix: str) -> int | None:
    if not callback_data.startswith(f"{prefix}:"):
        return None
    raw_id = callback_data[len(prefix) + 1 :]
    try:
        return int(raw_id)
    except ValueError:
        return None


async def _get_active_account(
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    telegram_user_id: int,
) -> NovaPoshtaAccount | None:
    return await nova_poshta_account_repository.get_active_account(telegram_user_id)


async def show_payment_cards_list(
    message: Message,
    payment_card_repository: PaymentCardRepository,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    *,
    cards: list[PaymentCard] | None = None,
    telegram_user_id: int | None = None,
    active_account: NovaPoshtaAccount | None = None,
) -> None:
    """Render saved payment cards for the active Nova Poshta account."""
    user_id = telegram_user_id
    if user_id is None:
        if message.from_user is None:
            return
        user_id = message.from_user.id

    account = active_account
    if account is None:
        account = await _get_active_account(nova_poshta_account_repository, user_id)
    if account is None:
        await message.answer(MSG_NO_ACTIVE_NP_ACCOUNT)
        return

    if cards is None:
        cards = await payment_card_repository.get_all_cards(
            user_id,
            nova_poshta_account_id=account.id,
            nova_poshta_account_name=account.account_name,
        )

    if not cards:
        await message.answer(
            MSG_CARDS_EMPTY,
            reply_markup=build_payment_cards_footer_keyboard(),
        )
        return

    await message.answer(MSG_CARDS_LIST_HEADER)
    for card in cards:
        await message.answer(
            format_payment_card(card),
            reply_markup=build_payment_card_actions_keyboard(card.id),
        )

    await message.answer(
        MSG_CARDS_FOOTER,
        reply_markup=build_payment_cards_footer_keyboard(),
    )


async def begin_payment_cards_list(
    message: Message,
    state: FSMContext,
    payment_card_repository: PaymentCardRepository,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
) -> None:
    """Open the payment cards section."""
    await state.clear()
    await show_payment_cards_list(
        message,
        payment_card_repository,
        nova_poshta_account_repository,
    )


@router.callback_query(F.data == CALLBACK_CARD_ADD)
async def handle_payment_card_add_start(
    callback: CallbackQuery,
    state: FSMContext,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    active_account = await _get_active_account(
        nova_poshta_account_repository,
        callback.from_user.id,
    )
    if active_account is None:
        await callback.answer()
        await callback.message.answer(MSG_NO_ACTIVE_NP_ACCOUNT)
        return

    await state.clear()
    await state.set_state(PaymentCardWizard.add_name)
    await state.update_data(nova_poshta_account_id=active_account.id)
    await callback.answer()
    await callback.message.answer(MSG_CARD_ASK_NAME)


@router.message(PaymentCardWizard.add_name, F.text)
async def handle_payment_card_add_name(
    message: Message,
    state: FSMContext,
) -> None:
    if message.text is None or not message.text.strip():
        await message.answer(MSG_CARD_ASK_NAME)
        return

    await state.update_data(card_name=message.text.strip())
    await state.set_state(PaymentCardWizard.add_owner)
    await message.answer(MSG_CARD_ASK_OWNER)


@router.message(PaymentCardWizard.add_owner, F.text)
async def handle_payment_card_add_owner(
    message: Message,
    state: FSMContext,
) -> None:
    if message.text is None or not message.text.strip():
        await message.answer(MSG_CARD_ASK_OWNER)
        return

    await state.update_data(owner_name=message.text.strip())
    await state.set_state(PaymentCardWizard.add_number)
    await message.answer(MSG_CARD_ASK_NUMBER)


@router.message(PaymentCardWizard.add_number, F.text)
async def handle_payment_card_add_number(
    message: Message,
    state: FSMContext,
    payment_card_repository: PaymentCardRepository,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
) -> None:
    if message.from_user is None or message.text is None:
        return

    card_number = validate_card_number(message.text)
    if card_number is None:
        await message.answer(MSG_CARD_INVALID_NUMBER)
        return

    data = await state.get_data()
    card_name = str(data.get("card_name") or "").strip()
    owner_name = str(data.get("owner_name") or "").strip()
    account_id = data.get("nova_poshta_account_id")
    if not card_name:
        await state.set_state(PaymentCardWizard.add_name)
        await message.answer(MSG_CARD_ASK_NAME)
        return
    if not owner_name:
        await state.set_state(PaymentCardWizard.add_owner)
        await message.answer(MSG_CARD_ASK_OWNER)
        return

    active_account = await _get_active_account(
        nova_poshta_account_repository,
        message.from_user.id,
    )
    if active_account is None:
        await state.clear()
        await message.answer(MSG_NO_ACTIVE_NP_ACCOUNT)
        return

    resolved_account_id = int(account_id) if account_id is not None else active_account.id
    if resolved_account_id != active_account.id:
        resolved_account_id = active_account.id

    await payment_card_repository.create_card(
        telegram_user_id=message.from_user.id,
        nova_poshta_account_id=resolved_account_id,
        card_name=card_name,
        card_ref="",
        owner_name=owner_name,
        card_number=card_number,
        nova_poshta_account_name=active_account.account_name,
    )

    await state.clear()
    await message.answer(MSG_CARD_SAVED)
    await show_payment_cards_list(
        message,
        payment_card_repository,
        nova_poshta_account_repository,
        active_account=active_account,
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_CARD_SELECT}:"))
async def handle_payment_card_select(
    callback: CallbackQuery,
    payment_card_repository: PaymentCardRepository,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        return

    active_account = await _get_active_account(
        nova_poshta_account_repository,
        callback.from_user.id,
    )
    if active_account is None:
        await callback.answer()
        await callback.message.answer(MSG_NO_ACTIVE_NP_ACCOUNT)
        return

    card_id = _parse_card_id(callback.data, CALLBACK_CARD_SELECT)
    if card_id is None:
        await callback.answer("Некоректна картка", show_alert=True)
        return

    card = await payment_card_repository.set_active_card(
        card_id,
        callback.from_user.id,
        nova_poshta_account_id=active_account.id,
        nova_poshta_account_name=active_account.account_name,
    )
    await callback.answer()
    if card is None:
        await callback.message.answer(MSG_CARDS_EMPTY)
        return

    await callback.message.answer(MSG_CARD_ACTIVE_CHANGED)
    await show_payment_cards_list(
        callback.message,
        payment_card_repository,
        nova_poshta_account_repository,
        telegram_user_id=callback.from_user.id,
        active_account=active_account,
    )


@router.callback_query(
    F.data.startswith(f"{CALLBACK_CARD_DELETE}:")
    & ~F.data.startswith(f"{CALLBACK_CARD_DELETE_YES}:")
    & ~F.data.startswith(f"{CALLBACK_CARD_DELETE_NO}:"),
)
async def handle_payment_card_delete_prompt(callback: CallbackQuery) -> None:
    if callback.data is None or callback.message is None:
        return

    card_id = _parse_card_id(callback.data, CALLBACK_CARD_DELETE)
    if card_id is None:
        await callback.answer("Некоректна картка", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        MSG_CARD_DELETE_CONFIRM,
        reply_markup=build_payment_card_delete_keyboard(card_id),
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_CARD_DELETE_YES}:"))
async def handle_payment_card_delete_confirm(
    callback: CallbackQuery,
    payment_card_repository: PaymentCardRepository,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        return

    active_account = await _get_active_account(
        nova_poshta_account_repository,
        callback.from_user.id,
    )
    if active_account is None:
        await callback.answer()
        await callback.message.answer(MSG_NO_ACTIVE_NP_ACCOUNT)
        return

    card_id = _parse_card_id(callback.data, CALLBACK_CARD_DELETE_YES)
    if card_id is None:
        await callback.answer("Некоректна картка", show_alert=True)
        return

    deleted = await payment_card_repository.delete_card(
        card_id,
        callback.from_user.id,
        nova_poshta_account_id=active_account.id,
        nova_poshta_account_name=active_account.account_name,
    )
    await callback.answer()
    if not deleted:
        await callback.message.answer(MSG_CARDS_EMPTY)
        return

    await callback.message.answer(MSG_CARD_DELETED)
    await show_payment_cards_list(
        callback.message,
        payment_card_repository,
        nova_poshta_account_repository,
        telegram_user_id=callback.from_user.id,
        active_account=active_account,
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_CARD_DELETE_NO}:"))
async def handle_payment_card_delete_cancel(callback: CallbackQuery) -> None:
    if callback.message is None:
        return

    await callback.answer()
    await callback.message.answer(
        MSG_ACTION_CANCELLED,
        reply_markup=build_main_menu_keyboard(),
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_CARD_EDIT}:"))
async def handle_payment_card_edit_start(
    callback: CallbackQuery,
    state: FSMContext,
    payment_card_repository: PaymentCardRepository,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        return

    active_account = await _get_active_account(
        nova_poshta_account_repository,
        callback.from_user.id,
    )
    if active_account is None:
        await callback.answer()
        await callback.message.answer(MSG_NO_ACTIVE_NP_ACCOUNT)
        return

    card_id = _parse_card_id(callback.data, CALLBACK_CARD_EDIT)
    if card_id is None:
        await callback.answer("Некоректна картка", show_alert=True)
        return

    card = await payment_card_repository.get_by_id(
        card_id,
        callback.from_user.id,
        nova_poshta_account_id=active_account.id,
        nova_poshta_account_name=active_account.account_name,
    )
    if card is None:
        await callback.answer("Некоректна картка", show_alert=True)
        return

    await state.clear()
    await state.set_state(PaymentCardWizard.edit_name)
    await state.update_data(
        card_id=card_id,
        nova_poshta_account_id=active_account.id,
    )
    await callback.answer()
    await callback.message.answer(MSG_CARD_EDIT_NAME)


@router.message(PaymentCardWizard.edit_name, F.text)
async def handle_payment_card_edit_name(message: Message, state: FSMContext) -> None:
    if message.text is None or not message.text.strip():
        await message.answer(MSG_CARD_EDIT_NAME)
        return

    await state.update_data(card_name=message.text.strip())
    await state.set_state(PaymentCardWizard.edit_owner)
    await message.answer(MSG_CARD_EDIT_OWNER)


@router.message(PaymentCardWizard.edit_owner, F.text)
async def handle_payment_card_edit_owner(message: Message, state: FSMContext) -> None:
    if message.text is None or not message.text.strip():
        await message.answer(MSG_CARD_EDIT_OWNER)
        return

    await state.update_data(owner_name=message.text.strip())
    await state.set_state(PaymentCardWizard.edit_number)
    await message.answer(MSG_CARD_EDIT_NUMBER)


@router.message(PaymentCardWizard.edit_number, F.text)
async def handle_payment_card_edit_number(
    message: Message,
    state: FSMContext,
    payment_card_repository: PaymentCardRepository,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
) -> None:
    if message.from_user is None or message.text is None:
        return

    card_number = validate_card_number(message.text)
    if card_number is None:
        await message.answer(MSG_CARD_INVALID_NUMBER)
        return

    data = await state.get_data()
    card_id = data.get("card_id")
    card_name = str(data.get("card_name") or "").strip()
    owner_name = str(data.get("owner_name") or "").strip()
    account_id = data.get("nova_poshta_account_id")
    if card_id is None or not card_name or not owner_name:
        await state.clear()
        await message.answer(MSG_CARDS_EMPTY, reply_markup=build_main_menu_keyboard())
        return

    active_account = await _get_active_account(
        nova_poshta_account_repository,
        message.from_user.id,
    )
    if active_account is None:
        await state.clear()
        await message.answer(MSG_NO_ACTIVE_NP_ACCOUNT, reply_markup=build_main_menu_keyboard())
        return

    resolved_account_id = int(account_id) if account_id is not None else active_account.id
    if resolved_account_id != active_account.id:
        resolved_account_id = active_account.id

    updated = await payment_card_repository.update_card(
        int(card_id),
        message.from_user.id,
        nova_poshta_account_id=resolved_account_id,
        card_name=card_name,
        card_ref="",
        owner_name=owner_name,        card_number=card_number,
        nova_poshta_account_name=active_account.account_name,
    )

    await state.clear()
    if updated is None:
        await message.answer(MSG_CARDS_EMPTY, reply_markup=build_main_menu_keyboard())
        return

    await message.answer(MSG_CARD_UPDATED)
    await show_payment_cards_list(
        message,
        payment_card_repository,
        nova_poshta_account_repository,
        active_account=active_account,
    )


@router.callback_query(F.data == CALLBACK_CARD_BACK)
async def handle_payment_cards_back(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await state.clear()
    await callback.answer()
    await callback.message.answer(
        MSG_MAIN_MENU,
        reply_markup=build_main_menu_keyboard(),
    )
