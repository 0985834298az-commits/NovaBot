from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.constants import (
    BTN_CARDS,
    BTN_CREATE_TTN,
    BTN_MY_WAYBILLS,
    BTN_NP_ACCOUNTS,
    BTN_RECIPIENTS,
    BTN_SETTINGS,
    NP_ACCOUNTS_MENU_BUTTONS,
)
from app.handlers.settings import show_settings
from app.handlers.nova_poshta_accounts import begin_nova_poshta_accounts_list
from app.handlers.payment_cards import begin_payment_cards_list
from app.handlers.recipients import begin_recipients_list
from app.services.waybill_list_service import render_my_waybills
from app.handlers.ttn import begin_ttn_wizard
from app.keyboards import build_main_menu_keyboard
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.order_item_repository import OrderItemRepository
from app.repositories.payment_card_repository import PaymentCardRepository
from app.repositories.recipient_repository import RecipientRepository
from app.repositories.user_repository import UserRepository
from app.repositories.waybill_repository import WaybillRepository

router = Router(name="menu")


@router.message(F.text == BTN_CREATE_TTN)
async def handle_create_ttn(
    message: Message,
    state: FSMContext,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    payment_card_repository: PaymentCardRepository,
) -> None:
    """Interrupt the current flow and start TTN creation."""
    await state.clear()
    await begin_ttn_wizard(
        message,
        state,
        nova_poshta_account_repository,
        payment_card_repository,
    )


@router.message(F.text == BTN_MY_WAYBILLS)
async def handle_my_waybills(
    message: Message,
    state: FSMContext,
    waybill_repository: WaybillRepository,
    order_item_repository: OrderItemRepository,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
) -> None:
    """Show active waybills."""
    await state.clear()
    await render_my_waybills(
        message,
        waybill_repository,
        order_item_repository,
        nova_poshta_account_repository,
    )


@router.message(F.text == BTN_RECIPIENTS)
async def handle_recipients(
    message: Message,
    state: FSMContext,
    recipient_repository: RecipientRepository,
) -> None:
    """Show saved recipients address book."""
    await begin_recipients_list(message, state, recipient_repository)


@router.message(F.text == BTN_CARDS)
async def handle_payment_cards(
    message: Message,
    state: FSMContext,
    payment_card_repository: PaymentCardRepository,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
) -> None:
    """Show saved payment cards."""
    await begin_payment_cards_list(
        message,
        state,
        payment_card_repository,
        nova_poshta_account_repository,
    )


@router.message(F.text.in_(NP_ACCOUNTS_MENU_BUTTONS))
async def handle_nova_poshta_accounts(
    message: Message,
    state: FSMContext,
    nova_poshta_account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
) -> None:
    """Show saved Nova Poshta accounts."""
    await state.clear()
    await message.answer(
        BTN_NP_ACCOUNTS,
        reply_markup=build_main_menu_keyboard(),
    )
    await begin_nova_poshta_accounts_list(
        message,
        state,
        nova_poshta_account_repository,
        waybill_repository,
    )


@router.message(F.text == BTN_SETTINGS)
async def handle_settings(
    message: Message,
    state: FSMContext,
    user_repository: UserRepository,
) -> None:
    """Show bot settings."""
    await state.clear()
    await show_settings(message, user_repository)
