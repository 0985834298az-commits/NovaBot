from app.handlers.api_key import router as api_key_router
from app.handlers.menu import router as menu_router
from app.handlers.start import router as start_router

__all__ = ("api_key_router", "menu_router", "start_router")
