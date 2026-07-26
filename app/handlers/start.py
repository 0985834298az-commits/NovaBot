from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.constants import START_MESSAGE

router = Router(name="start")


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """Welcome authorized users."""
    await message.answer(START_MESSAGE)
