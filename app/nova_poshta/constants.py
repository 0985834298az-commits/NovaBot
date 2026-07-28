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
MODEL_PAYMENT = "Payment"
MODEL_TRACKING_DOCUMENT = "TrackingDocument"

METHOD_GET_STATUS = "getServiceTypes"
METHOD_SEARCH_SETTLEMENTS = "searchSettlements"
METHOD_GET_WAREHOUSES = "getWarehouses"
METHOD_GET_COUNTERPARTIES = "getCounterparties"
METHOD_GET_CATALOG_COUNTERPARTY = "getCatalogCounterparty"
METHOD_GET_COUNTERPARTY_ADDRESSES = "getCounterpartyAddresses"
METHOD_GET_COUNTERPARTY_CONTACT_PERSONS = "getCounterpartyContactPersons"
METHOD_SAVE = "save"
METHOD_UPDATE = "update"
METHOD_DELETE = "delete"
METHOD_GET_STATUS_DOCUMENTS = "getStatusDocuments"
METHOD_GET_DOCUMENT_LIST = "getDocumentList"
METHOD_GET_DOCUMENT = "getDocument"
METHOD_INIT_PAYOUT = "initPayout"
METHOD_WALLET_MANAGEMENT = "walletManagement"

NP_API_SYSTEM = "PA 3.0"
NP_MERCHANT_DOMAIN = "new.novaposhta.ua"

DOCUMENT_LIST_PAGE_SIZE = "100"
DOCUMENT_LIST_SYNC_DAYS = 90

PRINT_DOCUMENT_URL = (
    "https://my.novaposhta.ua/orders/printDocument/orders[]/{document_ref}/type/pdf/apiKey/{api_key}"
)
