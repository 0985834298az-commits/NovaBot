import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.middlewares import AuthorizationMiddleware
from app.bot.middlewares.database import DatabaseMiddleware
from app.bot.session import create_http_session
from app.config.settings import Settings
from app.constants import VERSION
from app.database.session import (
    create_engine,
    create_session_factory,
    init_db,
)
from app.handlers import (
    account_selection_router,
    menu_router,
    nova_poshta_accounts_router,
    payment_cards_router,
    recipients_router,
    settings_router,
    start_router,
    ttn_router,
    waybills_router,
)
from app.services.waybill_tracker import run_waybill_status_checker


def create_bot(settings: Settings) -> Bot:
    """Create and configure the Telegram bot instance."""
    return Bot(
        token=settings.bot_token,
        session=create_http_session(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> Dispatcher:
    """Create dispatcher, register middleware, and attach routers."""
    dispatcher = Dispatcher()
    dispatcher.update.outer_middleware(
        AuthorizationMiddleware(settings.admin_ids),
    )
    dispatcher.update.middleware(DatabaseMiddleware(session_factory))
    dispatcher.include_router(start_router)
    dispatcher.include_router(menu_router)
    dispatcher.include_router(settings_router)
    dispatcher.include_router(nova_poshta_accounts_router)
    dispatcher.include_router(account_selection_router)
    dispatcher.include_router(payment_cards_router)
    dispatcher.include_router(waybills_router)
    dispatcher.include_router(recipients_router)
    dispatcher.include_router(ttn_router)
    return dispatcher


async def on_startup(settings: Settings) -> tuple[Bot, Dispatcher]:
    """Initialize dependencies and return bot with dispatcher."""
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    await init_db(engine)

    bot = create_bot(settings)
    dispatcher = create_dispatcher(settings, session_factory)

    dispatcher["engine"] = engine
    dispatcher["session_factory"] = session_factory

    dispatcher["waybill_tracker_task"] = asyncio.create_task(
        run_waybill_status_checker(session_factory),
    )

    logger.info("NovaBot {} started successfully", VERSION)
    return bot, dispatcher


async def on_shutdown(dispatcher: Dispatcher) -> None:
    """Release resources on shutdown."""
    tracker_task = dispatcher.get("waybill_tracker_task")
    if tracker_task is not None:
        tracker_task.cancel()
        try:
            await tracker_task
        except asyncio.CancelledError:
            pass

    engine = dispatcher.get("engine")
    if engine is not None:
        await engine.dispose()
        logger.info("Database engine disposed")
