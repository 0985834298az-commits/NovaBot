from aiogram.fsm.state import State, StatesGroup


class TtnWizard(StatesGroup):
    """Single-message TTN creation flow."""

    order_input = State()
    products_input = State()


class RecipientWizard(StatesGroup):
    """Recipient address book flows."""

    search = State()
    edit_name = State()
    edit_phone = State()
    edit_city = State()
    edit_warehouse = State()
    ttn_cod = State()
    products_input = State()


class WaybillWizard(StatesGroup):
    """Active waybill management flows."""

    edit_products = State()


class NovaPoshtaAccountWizard(StatesGroup):
    """Nova Poshta account management flows."""

    add_name = State()
    add_api_key = State()
    edit_name = State()
    edit_api_key = State()


class PaymentCardWizard(StatesGroup):
    """Payment card management flows."""

    add_name = State()
    add_owner = State()
    add_number = State()
    edit_name = State()
    edit_owner = State()
    edit_number = State()
