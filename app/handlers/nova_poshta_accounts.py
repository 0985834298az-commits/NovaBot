from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from app.constants import (
    CALLBACK_NP_ACCOUNT_ACTIVATE,
    CALLBACK_NP_ACCOUNT_ADD,
    CALLBACK_NP_ACCOUNT_BACK,
    CALLBACK_NP_ACCOUNT_CHANGE_API,
    CALLBACK_NP_ACCOUNT_DELETE,
    CALLBACK_NP_ACCOUNT_DELETE_NO,
    CALLBACK_NP_ACCOUNT_DELETE_YES,
    CALLBACK_NP_ACCOUNT_DETAIL_BACK,
    CALLBACK_NP_ACCOUNT_OPEN,
    CALLBACK_NP_ACCOUNT_RENAME,
    CALLBACK_NP_ACCOUNT_SYNC,
    MSG_NP_ACCOUNT_ACTIVE_CHANGED,
    MSG_NP_ACCOUNT_API_UPDATED,
    MSG_NP_ACCOUNT_DELETE_CONFIRM,
    MSG_NP_ACCOUNT_DELETED,
    MSG_NP_ACCOUNT_DETAIL_HEADER,
    MSG_NP_ACCOUNT_RENAMED,
    MSG_NP_ACCOUNT_SAVED,
    MSG_MAIN_MENU,
    MSG_NP_ACCOUNTS_EMPTY,
    MSG_NP_ACCOUNTS_FOOTER,
    MSG_NP_ACCOUNTS_LIST_HEADER,
    MSG_NP_ASK_ACCOUNT_NAME,
    MSG_NP_ASK_API_KEY,
    MSG_NP_INVALID_API_KEY,
    MSG_SYNC_COMPLETE,
    MSG_SYNC_FAILED,
    MSG_SYNC_IN_PROGRESS,
)
from app.handlers.states import NovaPoshtaAccountWizard
from app.keyboards import (
    build_main_menu_keyboard,
    build_nova_poshta_account_delete_keyboard,
    build_nova_poshta_account_detail_keyboard,
    build_nova_poshta_account_list_item_keyboard,
    build_nova_poshta_accounts_footer_keyboard,
)
from app.models.nova_poshta_account import NovaPoshtaAccount
from app.nova_poshta import NovaPoshtaClient
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.nova_poshta_account_service import (
    format_nova_poshta_account_with_usage,
)
from app.services.sender_cache import ensure_sender_cache, invalidate_sender_cache
from app.services.waybill_sync_service import sync_user_waybills

router = Router(name="np_accounts")


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
    waybill_repository: WaybillRepository,
    *,
    accounts: list[NovaPoshtaAccount] | None = None,
    sync_before_show: bool = False,
) -> None:
    """Render saved Nova Poshta accounts for the current Telegram user."""
    if message.from_user is None:
        return

    if sync_before_show:
        try:
            await sync_user_waybills(
                telegram_user_id=message.from_user.id,
                account_repository=account_repository,
                waybill_repository=waybill_repository,
            )
        except Exception as exc:
            logger.exception(
                "Automatic Nova Poshta sync failed for user {}: {}",
                message.from_user.id,
                exc,
            )

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
            await format_nova_poshta_account_with_usage(account, waybill_repository),
            reply_markup=build_nova_poshta_account_list_item_keyboard(account.id),
        )

    await message.answer(
        MSG_NP_ACCOUNTS_FOOTER,
        reply_markup=build_nova_poshta_accounts_footer_keyboard(),
    )


async def show_nova_poshta_account_detail(
    message: Message,
    account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
    account_id: int,
    telegram_user_id: int,
) -> None:
    """Render a single Nova Poshta account with management actions."""
    account = await account_repository.get_by_id(account_id, telegram_user_id)
    if account is None:
        await message.answer(MSG_NP_ACCOUNTS_EMPTY)
        await show_nova_poshta_accounts_list(
            message,
            account_repository,
            waybill_repository,
        )
        return

    account_text = await format_nova_poshta_account_with_usage(account, waybill_repository)
    await message.answer(
        f"{MSG_NP_ACCOUNT_DETAIL_HEADER}\n\n{account_text}",
        reply_markup=build_nova_poshta_account_detail_keyboard(account.id),
    )


async def begin_nova_poshta_accounts_list(
    message: Message,
    state: FSMContext,
    account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
    *,
    sync_before_show: bool = False,
) -> None:
    """Open the Nova Poshta accounts section."""
    await state.clear()
    await show_nova_poshta_accounts_list(
        message,
        account_repository,
        waybill_repository,
        sync_before_show=sync_before_show,
    )


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
    waybill_repository: WaybillRepository,
) -> None:
    if message.from_user is None or message.text is None:
        return

    api_key = message.text.strip()
    if not api_key:
        await message.answer(MSG_NP_INVALID_API_KEY)
        return

    account_name = str((await state.get_data()).get("account_name") or "").strip()
    if not account_name:
        await state.set_state(NovaPoshtaAccountWizard.add_name)
        await message.answer(MSG_NP_ASK_ACCOUNT_NAME)
        return

    logger.info("Validating Nova Poshta API key for user {}", message.from_user.id)
    if not await _validate_api_key(api_key):
        await message.answer(MSG_NP_INVALID_API_KEY)
        return

    await account_repository.create_account(
        telegram_user_id=message.from_user.id,
        account_name=account_name,
        api_key=api_key,
    )

    await ensure_sender_cache(message.from_user.id, api_key)

    await state.clear()
    await message.answer(MSG_NP_ACCOUNT_SAVED)
    await show_nova_poshta_accounts_list(message, account_repository, waybill_repository)


@router.callback_query(F.data.startswith(f"{CALLBACK_NP_ACCOUNT_OPEN}:"))
async def handle_nova_poshta_account_open(
    callback: CallbackQuery,
    account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        return

    account_id = _parse_account_id(callback.data, CALLBACK_NP_ACCOUNT_OPEN)
    if account_id is None:
        await callback.answer("Некоректний акаунт", show_alert=True)
        return

    await callback.answer()
    await show_nova_poshta_account_detail(
        callback.message,
        account_repository,
        waybill_repository,
        account_id,
        callback.from_user.id,
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_NP_ACCOUNT_ACTIVATE}:"))
async def handle_nova_poshta_account_activate(
    callback: CallbackQuery,
    account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        return

    account_id = _parse_account_id(callback.data, CALLBACK_NP_ACCOUNT_ACTIVATE)
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
    await ensure_sender_cache(callback.from_user.id, account.api_key)
    await show_nova_poshta_account_detail(
        callback.message,
        account_repository,
        waybill_repository,
        account_id,
        callback.from_user.id,
    )


@router.callback_query(F.data == CALLBACK_NP_ACCOUNT_DETAIL_BACK)
async def handle_nova_poshta_account_detail_back(
    callback: CallbackQuery,
    account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    await callback.answer()
    await show_nova_poshta_accounts_list(callback.message, account_repository, waybill_repository)


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
    waybill_repository: WaybillRepository,
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

    invalidate_sender_cache(callback.from_user.id)
    active_account = await account_repository.get_active_account(callback.from_user.id)
    if active_account is not None:
        await ensure_sender_cache(callback.from_user.id, active_account.api_key)

    await callback.message.answer(MSG_NP_ACCOUNT_DELETED)
    await show_nova_poshta_accounts_list(callback.message, account_repository, waybill_repository)


@router.callback_query(F.data.startswith(f"{CALLBACK_NP_ACCOUNT_DELETE_NO}:"))
async def handle_nova_poshta_account_delete_cancel(
    callback: CallbackQuery,
    account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        return

    account_id = _parse_account_id(callback.data, CALLBACK_NP_ACCOUNT_DELETE_NO)
    await callback.answer()
    if account_id is None:
        await show_nova_poshta_accounts_list(callback.message, account_repository, waybill_repository)
        return

    await show_nova_poshta_account_detail(
        callback.message,
        account_repository,
        waybill_repository,
        account_id,
        callback.from_user.id,
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
    waybill_repository: WaybillRepository,
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
    await show_nova_poshta_account_detail(
        message,
        account_repository,
        waybill_repository,
        int(account_id),
        message.from_user.id,
    )


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
    waybill_repository: WaybillRepository,
) -> None:
    if message.from_user is None or message.text is None:
        return

    api_key = message.text.strip()
    if not api_key:
        await message.answer(MSG_NP_INVALID_API_KEY)
        return

    data = await state.get_data()
    account_id = data.get("account_id")
    if account_id is None:
        await state.clear()
        await message.answer(MSG_NP_ACCOUNTS_EMPTY, reply_markup=build_main_menu_keyboard())
        return

    logger.info("Validating Nova Poshta API key for user {}", message.from_user.id)
    if not await _validate_api_key(api_key):
        await message.answer(MSG_NP_INVALID_API_KEY)
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

    invalidate_sender_cache(message.from_user.id)
    await ensure_sender_cache(message.from_user.id, api_key)

    await message.answer(MSG_NP_ACCOUNT_API_UPDATED)
    await show_nova_poshta_account_detail(
        message,
        account_repository,
        waybill_repository,
        int(account_id),
        message.from_user.id,
    )


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
        MSG_MAIN_MENU,
        reply_markup=build_main_menu_keyboard(),
    )


@router.callback_query(F.data == CALLBACK_NP_ACCOUNT_SYNC)
async def handle_nova_poshta_account_sync(
    callback: CallbackQuery,
    account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    await callback.answer()
    progress_message = await callback.message.answer(MSG_SYNC_IN_PROGRESS)
    try:
        result = await sync_user_waybills(
            telegram_user_id=callback.from_user.id,
            account_repository=account_repository,
            waybill_repository=waybill_repository,
        )
    except Exception as exc:
        logger.exception(
            "Manual Nova Poshta sync failed for user {}: {}",
            callback.from_user.id,
            exc,
        )
        await progress_message.edit_text(MSG_SYNC_FAILED)
        return

    active_account = await account_repository.get_active_account(callback.from_user.id)
    if active_account and active_account.account_name in result.failed_accounts:
        logger.error(
            "Manual Nova Poshta sync failed for user {}: active account {} failed",
            callback.from_user.id,
            active_account.account_name,
        )
        await progress_message.edit_text(MSG_SYNC_FAILED)
        return

    await progress_message.edit_text(
        MSG_SYNC_COMPLETE.format(
            added=result.added,
            updated=result.updated,
            deleted=result.deleted,
        ),
    )
    await show_nova_poshta_accounts_list(
        callback.message,
        account_repository,
        waybill_repository,
    )
