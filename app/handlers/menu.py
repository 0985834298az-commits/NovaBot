from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.constants import (
    ASK_API_KEY_MESSAGE,
    BTN_API_KEY,
    BTN_CARDS,
    BTN_CREATE_TTN,
    BTN_MY_WAYBILLS,
    BTN_RECIPIENTS,
    BTN_SETTINGS,
    MSG_SETTINGS_SOON,
    API_KEY_VISIBLE_CHARS,
)
from app.handlers.payment_cards import begin_payment_cards_list
from app.handlers.recipients import begin_recipients_list
from app.handlers.waybills import show_active_waybills
from app.handlers.states import WaitingForApiKey
from app.handlers.ttn import begin_ttn_wizard
from app.keyboards import build_main_menu_keyboard, build_replace_api_key_keyboard
from app.repositories.order_item_repository import OrderItemRepository
from app.repositories.payment_card_repository import PaymentCardRepository
from app.repositories.recipient_repository import RecipientRepository
from app.repositories.waybill_repository import WaybillRepository
from app.repositories.user_repository import UserRepository
from app.utils.api_key import mask_api_key

router = Router(name="menu")


@router.message(F.text == BTN_CREATE_TTN)
async def handle_create_ttn(
    message: Message,
    state: FSMContext,
    user_repository: UserRepository,
    payment_card_repository: PaymentCardRepository,
) -> None:
    """Interrupt the current flow and start TTN creation."""
    await state.clear()
    await begin_ttn_wizard(message, state, user_repository, payment_card_repository)


@router.message(F.text == BTN_MY_WAYBILLS)
async def handle_my_waybills(
    message: Message,
    state: FSMContext,
    waybill_repository: WaybillRepository,
    order_item_repository: OrderItemRepository,
) -> None:
    """Show active waybills."""
    await state.clear()
    await show_active_waybills(message, waybill_repository, order_item_repository)


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
) -> None:
    """Show saved payment cards."""
    await begin_payment_cards_list(message, state, payment_card_repository)


@router.message(F.text == BTN_API_KEY)
async def handle_api_key_menu(
    message: Message,
    user_repository: UserRepository,
    state: FSMContext,
) -> None:
    """Show stored API key or ask the user to enter one."""
    await state.clear()

    if message.from_user is None:
        return

    user = await user_repository.get_user(message.from_user.id)

    if user is None or not user.api_key:
        await state.set_state(WaitingForApiKey.api_key)
        await message.answer(ASK_API_KEY_MESSAGE)
        return

    masked_key = mask_api_key(user.api_key, API_KEY_VISIBLE_CHARS)
    await message.answer(
        masked_key,
        reply_markup=build_replace_api_key_keyboard(),
    )


@router.message(F.text == BTN_SETTINGS)
async def handle_settings(message: Message, state: FSMContext) -> None:
    """Placeholder for bot settings."""
    await state.clear()
    await message.answer(
        MSG_SETTINGS_SOON,
        reply_markup=build_main_menu_keyboard(),
    )
