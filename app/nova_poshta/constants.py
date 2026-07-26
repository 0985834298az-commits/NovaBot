"""Nova Poshta API constants."""

API_URL = "https://api.novaposhta.ua/v2.0/json/"
DEFAULT_TIMEOUT_SECONDS = 30
SEARCH_LIMIT = "20"
SEARCH_PAGE = "1"

MODEL_COMMON = "Common"
MODEL_ADDRESS = "Address"
MODEL_COUNTERPARTY = "Counterparty"
MODEL_CONTACT_PERSON = "ContactPerson"
MODEL_INTERNET_DOCUMENT = "InternetDocument"

METHOD_GET_STATUS = "getServiceTypes"
METHOD_SEARCH_SETTLEMENTS = "searchSettlements"
METHOD_GET_WAREHOUSES = "getWarehouses"
METHOD_GET_COUNTERPARTIES = "getCounterparties"
METHOD_GET_CATALOG_COUNTERPARTY = "getCatalogCounterparty"
METHOD_GET_COUNTERPARTY_CONTACT_PERSONS = "getCounterpartyContactPersons"
METHOD_SAVE = "save"

PRINT_DOCUMENT_URL = (
    "https://my.novaposhta.ua/orders/printDocument/orders[]/{document_ref}/type/pdf/apiKey/{api_key}"
)
