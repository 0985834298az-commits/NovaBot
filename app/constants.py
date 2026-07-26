"""Application-wide constants."""

VERSION = "v0.2"

UNAUTHORIZED_MESSAGE = "⛔️ У вас немає доступу до NovaBot."

START_MESSAGE = (
    "👋 Вітаємо у NovaBot!\n\n"
    f"Version: {VERSION}\n\n"
    "Bot is ready."
)

ASK_API_KEY_MESSAGE = "Введіть API ключ Нової Пошти"
API_KEY_SAVED_MESSAGE = "✅ API ключ успішно збережено."
API_KEY_INVALID_MESSAGE = "❌ API ключ неправильний.\n\nСпробуйте ще раз."

BTN_CREATE_TTN = "📦 Створити ТТН"
BTN_MY_WAYBILLS = "📋 Мої накладні"
BTN_RECIPIENTS = "👥 Одержувачі"
BTN_API_KEY = "🔑 API ключ"
BTN_SETTINGS = "⚙️ Налаштування"
BTN_REPLACE_API_KEY = "Замінити API ключ"

MAIN_MENU_BUTTONS = frozenset(
    {
        BTN_CREATE_TTN,
        BTN_MY_WAYBILLS,
        BTN_RECIPIENTS,
        BTN_API_KEY,
        BTN_SETTINGS,
    }
)

CALLBACK_REPLACE_API_KEY = "replace_api_key"

MSG_CREATE_TTN_SOON = "Створення ТТН скоро буде доступне."
MSG_WAYBILLS_EMPTY = "Історія накладних порожня."
MSG_RECIPIENTS_EMPTY = "Список одержувачів порожній."
MSG_SETTINGS_SOON = "Налаштування скоро будуть доступні."

API_KEY_MASK_SUFFIX = "****"
API_KEY_VISIBLE_CHARS = 8

# TTN wizard messages
MSG_TTN_ASK_SENDER_CITY = "Введіть місто відправника:"
MSG_TTN_ASK_SENDER_WAREHOUSE = "Введіть номер або адресу відділення відправника:"
MSG_TTN_ASK_RECIPIENT_NAME = "Введіть ПІБ одержувача:"
MSG_TTN_ASK_RECIPIENT_PHONE = "Введіть телефон одержувача:"
MSG_TTN_ASK_RECIPIENT_CITY = "Введіть місто одержувача:"
MSG_TTN_ASK_RECIPIENT_WAREHOUSE = "Введіть номер або адресу відділення одержувача:"
MSG_TTN_ASK_CARGO_DESCRIPTION = "Введіть опис вантажу:"
MSG_TTN_ASK_WEIGHT = "Введіть вагу вантажу (кг):"
MSG_TTN_ASK_DECLARED_COST = "Введіть оціночну вартість (грн):"
MSG_TTN_NO_CITIES = "Населений пункт не знайдено. Спробуйте інший запит."
MSG_TTN_NO_WAREHOUSES = "Відділення не знайдено. Спробуйте інший запит."
MSG_TTN_INVALID_PHONE = "Невірний формат телефону. Приклад: 0671234567"
MSG_TTN_INVALID_WEIGHT = "Невірна вага. Введіть число більше 0."
MSG_TTN_INVALID_COST = "Невірна оціночна вартість. Введіть число більше 0."
MSG_TTN_CANCELLED = "Створення ТТН скасовано."
MSG_TTN_CREATING = "Створюємо ТТН..."
MSG_TTN_CREATED = (
    "✅ ТТН успішно створено!\n\n"
    "Номер: <b>{ttn_number}</b>\n"
    "Reference: <code>{reference}</code>"
)
MSG_TTN_PRINT_LINK = "🖨 Посилання на друк: {link}"
MSG_TTN_CREATE_FAILED = "❌ Не вдалося створити ТТН:\n{error}"
MSG_TTN_EDIT_PROMPT = "Оберіть поле для редагування:"
MSG_TTN_NEED_API_KEY = "Спочатку додайте API ключ Нової Пошти."

# TTN wizard buttons
BTN_TTN_CREATE = "✅ Create TTN"
BTN_TTN_EDIT = "✏️ Edit"
BTN_TTN_CANCEL = "❌ Cancel"

# TTN callback prefixes
CALLBACK_TTN_CITY = "ttn:city"
CALLBACK_TTN_WAREHOUSE = "ttn:wh"
CALLBACK_TTN_REVIEW_CREATE = "ttn:review:create"
CALLBACK_TTN_REVIEW_EDIT = "ttn:review:edit"
CALLBACK_TTN_REVIEW_CANCEL = "ttn:review:cancel"
CALLBACK_TTN_EDIT_FIELD = "ttn:edit"

TTN_EDIT_FIELDS: dict[str, tuple[str, str]] = {
    "sender_city": ("Місто відправника", "sender_city"),
    "sender_warehouse": ("Відділення відправника", "sender_warehouse"),
    "recipient_name": ("ПІБ одержувача", "recipient_name"),
    "recipient_phone": ("Телефон одержувача", "recipient_phone"),
    "recipient_city": ("Місто одержувача", "recipient_city"),
    "recipient_warehouse": ("Відділення одержувача", "recipient_warehouse"),
    "cargo_description": ("Опис вантажу", "cargo_description"),
    "weight": ("Вага", "weight"),
    "declared_cost": ("Оціночна вартість", "declared_cost"),
}
