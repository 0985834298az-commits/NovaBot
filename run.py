import asyncio
import sys

import truststore

# Use the Windows certificate store before any HTTPS client modules initialize SSL.
truststore.inject_into_ssl()

from loguru import logger

from app.bot.main import on_shutdown, on_startup
from app.config.settings import LOGS_DIR, Settings
from app.utils.logging import setup_logging


async def main() -> None:
    """Application entry point."""
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    setup_logging(settings.log_level, LOGS_DIR)

    bot, dispatcher = await on_startup(settings)

    try:
        await dispatcher.start_polling(bot)
    finally:
        await on_shutdown(dispatcher)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
