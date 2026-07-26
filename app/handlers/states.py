from aiogram.fsm.state import State, StatesGroup


class WaitingForApiKey(StatesGroup):
    """Collect a Nova Poshta API key from the user."""

    api_key = State()


class TtnWizard(StatesGroup):
    """Multi-step TTN creation wizard."""

    sender_city = State()
    sender_warehouse = State()
    recipient_name = State()
    recipient_phone = State()
    recipient_city = State()
    recipient_warehouse = State()
    cargo_description = State()
    weight = State()
    declared_cost = State()
    review = State()
    edit_field = State()
