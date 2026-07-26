from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="start")

START_MESSAGE = "NovaBot v0.1 started successfully"


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """Reply to the /start command."""
    await message.answer(START_MESSAGE)
