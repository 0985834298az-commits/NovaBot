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
BTN_CARDS = "💳 Картки"
BTN_API_KEY = "🔑 API ключ"
BTN_SETTINGS = "⚙️ Налаштування"
BTN_REPLACE_API_KEY = "Замінити API ключ"

MAIN_MENU_BUTTONS = frozenset(
    {
        BTN_CREATE_TTN,
        BTN_MY_WAYBILLS,
        BTN_RECIPIENTS,
        BTN_CARDS,
        BTN_API_KEY,
        BTN_SETTINGS,
    }
)

CALLBACK_REPLACE_API_KEY = "replace_api_key"

MSG_CREATE_TTN_SOON = "Створення ТТН скоро буде доступне."
MSG_WAYBILLS_EMPTY = "Історія накладних порожня."
MSG_WAYBILLS_LIST_HEADER = "Активні накладні:"
WAYBILL_INITIAL_STATUS = "Створено"
WAYBILL_INITIAL_STATUS_CODE = "1"
WAYBILL_CHECK_INTERVAL_SECONDS = 300
MSG_RECIPIENTS_EMPTY = "Список одержувачів порожній."
MSG_RECIPIENTS_LIST_HEADER = "Збережені одержувачі:"
MSG_RECIPIENTS_SEARCH_PROMPT = "Введіть частину імені або телефону:"
MSG_RECIPIENTS_SEARCH_EMPTY = "Одержувачів за вашим запитом не знайдено."
MSG_RECIPIENTS_TRUNCATED = "Показано {shown} з {total} одержувачів."
MSG_RECIPIENT_DELETE_CONFIRM = "Видалити одержувача?"
MSG_RECIPIENT_DELETED = "Одержувача видалено."
MSG_RECIPIENT_UPDATED = "Дані одержувача оновлено."
MSG_RECIPIENT_ASK_COD = "Введіть накладений платіж:"
MSG_RECIPIENT_EDIT_NAME = "Введіть нове ПІБ:"
MSG_RECIPIENT_EDIT_PHONE = "Введіть новий телефон:"
MSG_RECIPIENT_EDIT_CITY = "Введіть нове місто:"
MSG_RECIPIENT_EDIT_WAREHOUSE = "Введіть новий номер відділення:"
MSG_RECIPIENT_INVALID_PHONE = "Невірний формат телефону. Приклад: 0671234567"
MSG_RECIPIENT_INVALID_COD = "Невірна сума накладеного платежу. Введіть число більше 0."
MSG_SETTINGS_SOON = "Налаштування скоро будуть доступні."

BTN_RECIPIENT_CREATE_TTN = "📦 Створити ТТН"
BTN_RECIPIENT_EDIT = "✏️ Редагувати"
BTN_RECIPIENT_DELETE = "🗑 Видалити"
BTN_RECIPIENT_SEARCH = "🔍 Пошук"
BTN_RECIPIENT_DELETE_YES = "✅ Так"
BTN_RECIPIENT_DELETE_NO = "❌ Ні"

RECIPIENT_SEARCH_THRESHOLD = 20

CALLBACK_RECIPIENT_TTN = "recipient:ttn"
CALLBACK_RECIPIENT_EDIT = "recipient:edit"
CALLBACK_RECIPIENT_DELETE = "recipient:delete"
CALLBACK_RECIPIENT_DELETE_YES = "recipient:delete:yes"
CALLBACK_RECIPIENT_DELETE_NO = "recipient:delete:no"
CALLBACK_RECIPIENT_SEARCH = "recipient:search"

BTN_CARD_SELECT = "✅ Обрати"
BTN_CARD_EDIT = "✏️ Редагувати"
BTN_CARD_DELETE = "🗑 Видалити"
BTN_CARD_ADD = "➕ Додати картку"
BTN_BACK = "⬅️ Назад"
BTN_CARD_DELETE_YES = "✅ Так"
BTN_CARD_DELETE_NO = "❌ Ні"

CALLBACK_CARD_SELECT = "card:select"
CALLBACK_CARD_EDIT = "card:edit"
CALLBACK_CARD_DELETE = "card:delete"
CALLBACK_CARD_DELETE_YES = "card:delete:yes"
CALLBACK_CARD_DELETE_NO = "card:delete:no"
CALLBACK_CARD_ADD = "card:add"
CALLBACK_CARD_BACK = "card:back"

MSG_CARDS_EMPTY = "Список карток порожній."
MSG_CARDS_LIST_HEADER = "Збережені картки:"
MSG_CARD_ASK_OWNER = "Ім'я власника картки"
MSG_CARD_ASK_NUMBER = "Номер картки"
MSG_CARD_INVALID_NUMBER = "Невірний номер картки. Введіть рівно 16 цифр."
MSG_CARD_SAVED = "✅ Картку збережено."
MSG_CARD_ACTIVE_CHANGED = "✅ Активна картка змінена."
MSG_CARD_DELETE_CONFIRM = "Видалити картку?"
MSG_CARD_DELETED = "Картку видалено."
MSG_CARD_EDIT_NAME = "Введіть ім'я власника картки:"
MSG_CARD_EDIT_NUMBER = "Введіть номер картки:"
MSG_CARD_UPDATED = "Дані картки оновлено."
MSG_NO_ACTIVE_PAYMENT_CARD = "Спочатку додайте картку у розділі 💳 Картки."

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
