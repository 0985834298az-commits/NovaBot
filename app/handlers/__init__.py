from app.handlers.api_key import router as api_key_router
from app.handlers.menu import router as menu_router
from app.handlers.payment_cards import router as payment_cards_router
from app.handlers.recipients import router as recipients_router
from app.handlers.start import router as start_router
from app.handlers.ttn import router as ttn_router
from app.handlers.waybills import router as waybills_router

__all__ = (
    "api_key_router",
    "menu_router",
    "payment_cards_router",
    "recipients_router",
    "start_router",
    "ttn_router",
    "waybills_router",
)
