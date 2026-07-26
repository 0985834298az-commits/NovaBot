from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger

from app.bot.middlewares import AuthorizationMiddleware
from app.bot.session import create_http_session
from app.config.settings import Settings
from app.constants import VERSION
from app.database.session import (
    create_engine,
    create_session_factory,
    init_db,
)
from app.handlers import start_router


def create_bot(settings: Settings) -> Bot:
    """Create and configure the Telegram bot instance."""
    return Bot(
        token=settings.bot_token,
        session=create_http_session(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(settings: Settings) -> Dispatcher:
    """Create dispatcher, register middleware, and attach routers."""
    dispatcher = Dispatcher()
    dispatcher.update.outer_middleware(
        AuthorizationMiddleware(settings.admin_ids),
    )
    dispatcher.include_router(start_router)
    return dispatcher


async def on_startup(settings: Settings) -> tuple[Bot, Dispatcher]:
    """Initialize dependencies and return bot with dispatcher."""
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    await init_db(engine)

    bot = create_bot(settings)
    dispatcher = create_dispatcher(settings)

    dispatcher["engine"] = engine
    dispatcher["session_factory"] = session_factory

    logger.info("NovaBot {} started successfully", VERSION)
    return bot, dispatcher


async def on_shutdown(dispatcher: Dispatcher) -> None:
    """Release resources on shutdown."""
    engine = dispatcher.get("engine")
    if engine is not None:
        await engine.dispose()
        logger.info("Database engine disposed")
