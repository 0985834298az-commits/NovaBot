from aiogram.fsm.state import State, StatesGroup


class WaitingForApiKey(StatesGroup):
    """Collect a Nova Poshta API key from the user."""

    api_key = State()


class TtnWizard(StatesGroup):
    """Single-message TTN creation flow."""

    order_input = State()


class RecipientWizard(StatesGroup):
    """Recipient address book flows."""

    search = State()
    edit_name = State()
    edit_phone = State()
    edit_city = State()
    edit_warehouse = State()
    ttn_cod = State()
