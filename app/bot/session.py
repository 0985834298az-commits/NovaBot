from aiogram.client.session.aiohttp import AiohttpSession

from app.utils.ssl import create_ssl_context


def create_http_session() -> AiohttpSession:
    """Create an aiogram HTTP session with a verified SSL context."""
    session = AiohttpSession()
    session._connector_init["ssl"] = create_ssl_context()
    return session
