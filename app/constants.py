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

# Default sender settings
SENDER_CITY_QUERY = "Криве Озеро"
SENDER_CITY_AREA = "Миколаївська"
SENDER_WAREHOUSE_NUMBER = "1"

# TTN creation defaults
TTN_DEFAULT_CARGO_DESCRIPTION = "Косметика"
TTN_DEFAULT_WEIGHT = "1"
TTN_DEFAULT_DECLARED_COST = "500"

# TTN messages
MSG_TTN_ASK_ORDER = (
    "Надішліть дані одним повідомленням у форматі:\n\n"
    "ПІБ\n"
    "Телефон\n"
    "Місто\n"
    "Відділення\n"
    "Накладений платіж\n\n"
    "Приклад:\n\n"
    "Іван Петренко\n"
    "0671234567\n"
    "Криве Озеро\n"
    "1\n"
    "1200"
)
MSG_TTN_INVALID_ORDER_FORMAT = (
    "Невірний формат. Надішліть рівно 5 непорожніх рядків.\n\n"
    "Приклад:\n\n"
    "Іван Петренко\n"
    "0671234567\n"
    "Криве Озеро\n"
    "1\n"
    "1200"
)
MSG_TTN_NO_CITIES = "Населений пункт не знайдено. Спробуйте інший запит."
MSG_TTN_NO_WAREHOUSES = "Відділення не знайдено. Спробуйте інший запит."
MSG_TTN_CREATING = "Створюємо ТТН..."
MSG_TTN_PRINT_LINK = "🖨 Посилання на друк: {link}"
MSG_TTN_CREATE_FAILED = "❌ Не вдалося створити ТТН:\n{error}"
MSG_TTN_SENDER_NOT_CONFIGURED = (
    "❌ Відправника не налаштовано.\n\n{error}\n\n"
    "Зверніться до адміністратора."
)
MSG_TTN_NEED_API_KEY = "Спочатку додайте API ключ Нової Пошти."
