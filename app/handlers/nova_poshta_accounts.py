from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from app.constants import (
    API_KEY_INVALID_MESSAGE,
    CALLBACK_NP_ACCOUNT_ADD,
    CALLBACK_NP_ACCOUNT_BACK,
    CALLBACK_NP_ACCOUNT_CHANGE_API,
    CALLBACK_NP_ACCOUNT_DELETE,
    CALLBACK_NP_ACCOUNT_DELETE_NO,
    CALLBACK_NP_ACCOUNT_DELETE_YES,
    CALLBACK_NP_ACCOUNT_RENAME,
    CALLBACK_NP_ACCOUNT_SELECT,
    MSG_NP_ACCOUNT_ACTIVE_CHANGED,
    MSG_NP_ACCOUNT_API_UPDATED,
    MSG_NP_ACCOUNT_DELETE_CONFIRM,
    MSG_NP_ACCOUNT_DELETED,
    MSG_NP_ACCOUNT_RENAMED,
    MSG_NP_ACCOUNT_SAVED,
    MSG_NP_ACCOUNTS_EMPTY,
    MSG_NP_ACCOUNTS_LIST_HEADER,
    MSG_NP_ASK_ACCOUNT_NAME,
    MSG_NP_ASK_API_KEY,
)
from app.handlers.states import NovaPoshtaAccountWizard
from app.keyboards import (
    build_main_menu_keyboard,
    build_nova_poshta_account_actions_keyboard,
    build_nova_poshta_account_delete_keyboard,
    build_nova_poshta_accounts_footer_keyboard,
)
from app.models.nova_poshta_account import NovaPoshtaAccount
from app.nova_poshta import NovaPoshtaClient
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.services.nova_poshta_account_service import format_nova_poshta_account

router = Router(name="nova_poshta_accounts")


def _parse_account_id(callback_data: str, prefix: str) -> int | None:
    if not callback_data.startswith(f"{prefix}:"):
        return None
    raw_id = callback_data[len(prefix) + 1 :]
    try:
        return int(raw_id)
    except ValueError:
        return None


async def _validate_api_key(api_key: str) -> bool:
    async with NovaPoshtaClient(api_key) as client:
        return await client.validate_api_key()


async def show_nova_poshta_accounts_list(
    message: Message,
    account_repository: NovaPoshtaAccountRepository,
    *,
    accounts: list[NovaPoshtaAccount] | None = None,
) -> None:
    """Render saved Nova Poshta accounts for the current Telegram user."""
    if message.from_user is None:
        return

    if accounts is None:
        accounts = await account_repository.get_all_accounts(message.from_user.id)

    if not accounts:
        await message.answer(
            MSG_NP_ACCOUNTS_EMPTY,
            reply_markup=build_nova_poshta_accounts_footer_keyboard(),
        )
        return

    await message.answer(MSG_NP_ACCOUNTS_LIST_HEADER)
    for account in accounts:
        await message.answer(
            format_nova_poshta_account(account),
            reply_markup=build_nova_poshta_account_actions_keyboard(account.id),
        )

    await message.answer(
        "Керування акаунтами:",
        reply_markup=build_nova_poshta_accounts_footer_keyboard(),
    )


async def begin_nova_poshta_accounts_list(
    message: Message,
    state: FSMContext,
    account_repository: NovaPoshtaAccountRepository,
) -> None:
    """Open the Nova Poshta accounts section."""
    await state.clear()
    await show_nova_poshta_accounts_list(message, account_repository)


@router.callback_query(F.data == CALLBACK_NP_ACCOUNT_ADD)
async def handle_nova_poshta_account_add_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.message is None:
        return

    await state.clear()
    await state.set_state(NovaPoshtaAccountWizard.add_name)
    await callback.answer()
    await callback.message.answer(MSG_NP_ASK_ACCOUNT_NAME)


@router.message(NovaPoshtaAccountWizard.add_name, F.text)
async def handle_nova_poshta_account_add_name(
    message: Message,
    state: FSMContext,
) -> None:
    if message.text is None or not message.text.strip():
        await message.answer(MSG_NP_ASK_ACCOUNT_NAME)
        return

    await state.update_data(account_name=message.text.strip())
    await state.set_state(NovaPoshtaAccountWizard.add_api_key)
    await message.answer(MSG_NP_ASK_API_KEY)


@router.message(NovaPoshtaAccountWizard.add_api_key, F.text)
async def handle_nova_poshta_account_add_api_key(
    message: Message,
    state: FSMContext,
    account_repository: NovaPoshtaAccountRepository,
) -> None:
    if message.from_user is None or message.text is None:
        return

    api_key = message.text.strip()
    if not api_key:
        await message.answer(API_KEY_INVALID_MESSAGE)
        return

    account_name = str((await state.get_data()).get("account_name") or "").strip()
    if not account_name:
        await state.set_state(NovaPoshtaAccountWizard.add_name)
        await message.answer(MSG_NP_ASK_ACCOUNT_NAME)
        return

    logger.info("Validating Nova Poshta API key for user {}", message.from_user.id)
    if not await _validate_api_key(api_key):
        await message.answer(API_KEY_INVALID_MESSAGE)
        return

    await account_repository.create_account(
        telegram_user_id=message.from_user.id,
        account_name=account_name,
        api_key=api_key,
    )

    await state.clear()
    await message.answer(MSG_NP_ACCOUNT_SAVED)
    await show_nova_poshta_accounts_list(message, account_repository)


@router.callback_query(F.data.startswith(f"{CALLBACK_NP_ACCOUNT_SELECT}:"))
async def handle_nova_poshta_account_select(
    callback: CallbackQuery,
    account_repository: NovaPoshtaAccountRepository,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        return

    account_id = _parse_account_id(callback.data, CALLBACK_NP_ACCOUNT_SELECT)
    if account_id is None:
        await callback.answer("Некоректний акаунт", show_alert=True)
        return

    account = await account_repository.set_active_account(
        account_id,
        callback.from_user.id,
    )
    await callback.answer()
    if account is None:
        await callback.message.answer(MSG_NP_ACCOUNTS_EMPTY)
        return

    await callback.message.answer(MSG_NP_ACCOUNT_ACTIVE_CHANGED)
    await show_nova_poshta_accounts_list(callback.message, account_repository)


@router.callback_query(
    F.data.startswith(f"{CALLBACK_NP_ACCOUNT_DELETE}:")
    & ~F.data.startswith(f"{CALLBACK_NP_ACCOUNT_DELETE_YES}:")
    & ~F.data.startswith(f"{CALLBACK_NP_ACCOUNT_DELETE_NO}:"),
)
async def handle_nova_poshta_account_delete_prompt(callback: CallbackQuery) -> None:
    if callback.data is None or callback.message is None:
        return

    account_id = _parse_account_id(callback.data, CALLBACK_NP_ACCOUNT_DELETE)
    if account_id is None:
        await callback.answer("Некоректний акаунт", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        MSG_NP_ACCOUNT_DELETE_CONFIRM,
        reply_markup=build_nova_poshta_account_delete_keyboard(account_id),
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_NP_ACCOUNT_DELETE_YES}:"))
async def handle_nova_poshta_account_delete_confirm(
    callback: CallbackQuery,
    account_repository: NovaPoshtaAccountRepository,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        return

    account_id = _parse_account_id(callback.data, CALLBACK_NP_ACCOUNT_DELETE_YES)
    if account_id is None:
        await callback.answer("Некоректний акаунт", show_alert=True)
        return

    deleted = await account_repository.delete_account(account_id, callback.from_user.id)
    await callback.answer()
    if not deleted:
        await callback.message.answer(MSG_NP_ACCOUNTS_EMPTY)
        return

    await callback.message.answer(MSG_NP_ACCOUNT_DELETED)
    await show_nova_poshta_accounts_list(callback.message, account_repository)


@router.callback_query(F.data.startswith(f"{CALLBACK_NP_ACCOUNT_DELETE_NO}:"))
async def handle_nova_poshta_account_delete_cancel(callback: CallbackQuery) -> None:
    if callback.message is None:
        return

    await callback.answer()
    await callback.message.answer(
        "Скасовано.",
        reply_markup=build_main_menu_keyboard(),
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_NP_ACCOUNT_RENAME}:"))
async def handle_nova_poshta_account_rename_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.data is None or callback.message is None:
        return

    account_id = _parse_account_id(callback.data, CALLBACK_NP_ACCOUNT_RENAME)
    if account_id is None:
        await callback.answer("Некоректний акаунт", show_alert=True)
        return

    await state.clear()
    await state.set_state(NovaPoshtaAccountWizard.edit_name)
    await state.update_data(account_id=account_id)
    await callback.answer()
    await callback.message.answer(MSG_NP_ASK_ACCOUNT_NAME)


@router.message(NovaPoshtaAccountWizard.edit_name, F.text)
async def handle_nova_poshta_account_rename_save(
    message: Message,
    state: FSMContext,
    account_repository: NovaPoshtaAccountRepository,
) -> None:
    if message.from_user is None or message.text is None or not message.text.strip():
        await message.answer(MSG_NP_ASK_ACCOUNT_NAME)
        return

    data = await state.get_data()
    account_id = data.get("account_id")
    if account_id is None:
        await state.clear()
        await message.answer(MSG_NP_ACCOUNTS_EMPTY, reply_markup=build_main_menu_keyboard())
        return

    updated = await account_repository.update_account(
        int(account_id),
        message.from_user.id,
        account_name=message.text.strip(),
    )

    await state.clear()
    if updated is None:
        await message.answer(MSG_NP_ACCOUNTS_EMPTY, reply_markup=build_main_menu_keyboard())
        return

    await message.answer(MSG_NP_ACCOUNT_RENAMED)
    await show_nova_poshta_accounts_list(message, account_repository)


@router.callback_query(F.data.startswith(f"{CALLBACK_NP_ACCOUNT_CHANGE_API}:"))
async def handle_nova_poshta_account_change_api_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.data is None or callback.message is None:
        return

    account_id = _parse_account_id(callback.data, CALLBACK_NP_ACCOUNT_CHANGE_API)
    if account_id is None:
        await callback.answer("Некоректний акаунт", show_alert=True)
        return

    await state.clear()
    await state.set_state(NovaPoshtaAccountWizard.edit_api_key)
    await state.update_data(account_id=account_id)
    await callback.answer()
    await callback.message.answer(MSG_NP_ASK_API_KEY)


@router.message(NovaPoshtaAccountWizard.edit_api_key, F.text)
async def handle_nova_poshta_account_change_api_save(
    message: Message,
    state: FSMContext,
    account_repository: NovaPoshtaAccountRepository,
) -> None:
    if message.from_user is None or message.text is None:
        return

    api_key = message.text.strip()
    if not api_key:
        await message.answer(API_KEY_INVALID_MESSAGE)
        return

    data = await state.get_data()
    account_id = data.get("account_id")
    if account_id is None:
        await state.clear()
        await message.answer(MSG_NP_ACCOUNTS_EMPTY, reply_markup=build_main_menu_keyboard())
        return

    logger.info("Validating Nova Poshta API key for user {}", message.from_user.id)
    if not await _validate_api_key(api_key):
        await message.answer(API_KEY_INVALID_MESSAGE)
        return

    updated = await account_repository.update_account(
        int(account_id),
        message.from_user.id,
        api_key=api_key,
    )

    await state.clear()
    if updated is None:
        await message.answer(MSG_NP_ACCOUNTS_EMPTY, reply_markup=build_main_menu_keyboard())
        return

    await message.answer(MSG_NP_ACCOUNT_API_UPDATED)
    await show_nova_poshta_accounts_list(message, account_repository)


@router.callback_query(F.data == CALLBACK_NP_ACCOUNT_BACK)
async def handle_nova_poshta_accounts_back(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.message is None:
        return

    await state.clear()
    await callback.answer()
    await callback.message.answer(
        "Головне меню:",
        reply_markup=build_main_menu_keyboard(),
    )
