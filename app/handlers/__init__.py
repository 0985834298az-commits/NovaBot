from app.handlers.account_selection import router as account_selection_router
from app.handlers.menu import router as menu_router
from app.handlers.nova_poshta_accounts import router as nova_poshta_accounts_router
from app.handlers.payment_cards import router as payment_cards_router
from app.handlers.recipients import router as recipients_router
from app.handlers.settings import router as settings_router
from app.handlers.start import router as start_router
from app.handlers.ttn import router as ttn_router
from app.handlers.waybills import router as waybills_router

__all__ = (
    "account_selection_router",
    "menu_router",
    "nova_poshta_accounts_router",
    "payment_cards_router",
    "recipients_router",
    "settings_router",
    "start_router",
    "ttn_router",
    "waybills_router",
)
