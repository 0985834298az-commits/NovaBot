from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger

from app.constants import (
    ASK_API_KEY_MESSAGE,
    MSG_NO_ACTIVE_PAYMENT_CARD,
    MSG_TTN_ASK_ORDER,
    MSG_TTN_CREATE_FAILED,
    MSG_TTN_CREATING,
    MSG_TTN_INVALID_ORDER_FORMAT,
    MSG_TTN_NEED_API_KEY,
    MSG_TTN_PRINT_LINK,
    MSG_TTN_SENDER_NOT_CONFIGURED,
)
from app.handlers.states import TtnWizard, WaitingForApiKey
from app.keyboards import build_main_menu_keyboard
from app.nova_poshta import NovaPoshtaClient
from app.nova_poshta.exceptions import NovaPoshtaError
from app.repositories.payment_card_repository import PaymentCardRepository
from app.repositories.recipient_repository import RecipientRepository
from app.repositories.user_repository import UserRepository
from app.services.sender_cache import (
    get_cached_sender_location,
    get_sender_cache_error,
    is_sender_cache_ready,
)
from app.services.ttn_service import (
    build_print_link,
    create_internet_document,
    extract_recipient_save_fields,
    format_ttn_success_message,
    parse_ttn_order_message,
    prepare_wizard_data_from_order,
)

router = Router(name="ttn")


async def _get_api_key(
    user_repository: UserRepository,
    telegram_id: int,
) -> str | None:
    user = await user_repository.get_user(telegram_id)
    if user is None or not user.api_key:
        return None
    return user.api_key


def _sender_not_configured_message() -> str:
    error = get_sender_cache_error() or "Sender location is not configured"
    return MSG_TTN_SENDER_NOT_CONFIGURED.format(error=error)


async def begin_ttn_wizard(
    message: Message,
    state: FSMContext,
    user_repository: UserRepository,
    payment_card_repository: PaymentCardRepository,
) -> None:
    """Start single-message TTN creation."""
    if message.from_user is None:
        return

    if not is_sender_cache_ready():
        await message.answer(_sender_not_configured_message())
        return

    active_card = await payment_card_repository.get_active_card(message.from_user.id)
    if active_card is None:
        await message.answer(
            MSG_NO_ACTIVE_PAYMENT_CARD,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    user = await user_repository.get_user(message.from_user.id)
    if user is None or not user.api_key:
        await state.set_state(WaitingForApiKey.api_key)
        await message.answer(ASK_API_KEY_MESSAGE)
        return

    await state.clear()
    await state.set_state(TtnWizard.order_input)
    await message.answer(MSG_TTN_ASK_ORDER)


@router.message(TtnWizard.order_input, F.text)
async def handle_ttn_order_input(
    message: Message,
    state: FSMContext,
    user_repository: UserRepository,
    recipient_repository: RecipientRepository,
    payment_card_repository: PaymentCardRepository,
) -> None:
    """Parse one message and create a TTN immediately."""
    if message.from_user is None or message.text is None:
        return

    if not is_sender_cache_ready():
        await state.clear()
        await message.answer(
            _sender_not_configured_message(),
            reply_markup=build_main_menu_keyboard(),
        )
        return

    order = parse_ttn_order_message(message.text)
    if order is None:
        await message.answer(MSG_TTN_INVALID_ORDER_FORMAT)
        return

    api_key = await _get_api_key(user_repository, message.from_user.id)
    if api_key is None:
        await state.clear()
        await message.answer(
            MSG_TTN_NEED_API_KEY,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    active_card = await payment_card_repository.get_active_card(message.from_user.id)
    if active_card is None:
        await state.clear()
        await message.answer(
            MSG_NO_ACTIVE_PAYMENT_CARD,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    await message.answer(MSG_TTN_CREATING)

    try:
        sender_location = get_cached_sender_location()
        async with NovaPoshtaClient(api_key) as client:
            wizard_data, sender_profile = await prepare_wizard_data_from_order(
                client,
                order,
                sender_location,
            )
            wizard_data["payment_card_number"] = active_card.card_number
            document = await create_internet_document(
                client,
                wizard_data,
                sender_profile,
            )
    except NovaPoshtaError as exc:
        logger.error("TTN creation failed for user {}: {}", message.from_user.id, exc)
        await message.answer(MSG_TTN_CREATE_FAILED.format(error=str(exc)))
        return

    ttn_number = str(document.get("IntDocNumber") or "—")
    reference = str(document.get("Ref") or "")
    delivery_cost = document.get("CostOnSite") or document.get("DocumentCost")

    await recipient_repository.save_recipient(
        telegram_user_id=message.from_user.id,
        **extract_recipient_save_fields(wizard_data),
    )

    await state.clear()
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
