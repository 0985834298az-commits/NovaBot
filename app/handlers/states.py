from aiogram.fsm.state import State, StatesGroup


class WaitingForApiKey(StatesGroup):
    """Collect a Nova Poshta API key from the user."""

    api_key = State()


class TtnWizard(StatesGroup):
    """Single-message TTN creation flow."""

    order_input = State()
