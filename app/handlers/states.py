from aiogram.fsm.state import State, StatesGroup


class WaitingForApiKey(StatesGroup):
    """Collect a Nova Poshta API key from the user."""

    api_key = State()
