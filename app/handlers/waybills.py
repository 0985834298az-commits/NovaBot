from aiogram import Router
from aiogram.types import Message

from app.constants import MSG_WAYBILLS_EMPTY, MSG_WAYBILLS_LIST_HEADER
from app.keyboards import build_main_menu_keyboard
from app.repositories.waybill_repository import WaybillRepository
from app.services.waybill_service import format_active_waybills_message

router = Router(name="waybills")


async def show_active_waybills(
    message: Message,
    waybill_repository: WaybillRepository,
) -> None:
    """Render active waybills with dynamic numbering."""
    if message.from_user is None:
        return

    waybills = await waybill_repository.get_active(message.from_user.id)
    if not waybills:
        await message.answer(
            MSG_WAYBILLS_EMPTY,
            reply_markup=build_main_menu_keyboard(),
        )
        return

    await message.answer(
        f"{MSG_WAYBILLS_LIST_HEADER}\n\n{format_active_waybills_message(waybills)}",
        reply_markup=build_main_menu_keyboard(),
    )
