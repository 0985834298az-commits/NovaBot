"""Application-wide constants."""

VERSION = "v0.2"

UNAUTHORIZED_MESSAGE = "⛔️ У вас немає доступу до NovaBot."

START_MESSAGE = (
    "👋 Вітаємо у NovaBot!\n\n"
    f"Версія: {VERSION}\n\n"
    "Бот готовий до роботи."
)

MSG_NP_INVALID_API_KEY = "❌ API ключ неправильний.\n\nСпробуйте ще раз."

BTN_CREATE_TTN = "📦 Створити ТТН"
BTN_MY_WAYBILLS = "📄 Мої накладні"
BTN_RECIPIENTS = "👥 Одержувачі"
BTN_CARDS = "💳 Картки"
BTN_NP_ACCOUNTS = "🏢 Акаунти НП"
BTN_NP_ACCOUNTS_LEGACY = "🔑 API ключ"
BTN_SETTINGS = "⚙️ Налаштування"

NP_ACCOUNTS_MENU_BUTTONS = frozenset(
    {
        BTN_NP_ACCOUNTS,
        BTN_NP_ACCOUNTS_LEGACY,
    }
)

MAIN_MENU_BUTTONS = frozenset(
    {
        BTN_CREATE_TTN,
        BTN_MY_WAYBILLS,
        BTN_RECIPIENTS,
        BTN_CARDS,
        BTN_NP_ACCOUNTS,
        BTN_SETTINGS,
    }
)

MSG_WAYBILLS_LIST_HEADER = "📄 Мої накладні:"
MSG_WAYBILLS_EMPTY = "📄 Мої накладні:\n\nАктивних накладних немає."
MSG_WAYBILLS_FOOTER = "📄 Керування накладними:"
WAYBILL_INITIAL_STATUS = "🟡 Створена"
WAYBILL_INITIAL_STATUS_CODE = "1"
WAYBILL_DELETED_STATUS_CODES = frozenset({"2", "3"})
WAYBILL_LIST_ACTIVE_STATUS_CODES = frozenset(
    {
        "1",  # 🟡 Створена
        "4",
        "5",
        "6",
        "41",
        "104",  # 🚚 У дорозі
        "7",
        "8",
        "105",  # 📦 Прибула у відділення
    }
)
WAYBILL_CHECK_INTERVAL_SECONDS = 300

BTN_SYNC = "🔄 Синхронізувати"
CALLBACK_WAYBILL_SYNC = "waybill:sync"
CALLBACK_NP_ACCOUNT_SYNC = "np_account:sync"
MSG_SYNC_IN_PROGRESS = "🔄 Синхронізація..."
MSG_SYNC_COMPLETE = (
    "✅ Синхронізацію завершено\n\n"
    "Додано: {added}\n\n"
    "Оновлено: {updated}\n\n"
    "Видалено: {deleted}"
)
MSG_SYNC_FAILED = (
    "⚠️ Не вдалося синхронізувати дані.\n\n"
    "Повторіть пізніше."
)

MSG_RECIPIENTS_EMPTY = "👥 Список одержувачів порожній."
MSG_RECIPIENTS_LIST_HEADER = "👥 Одержувачі:"
MSG_RECIPIENTS_SEARCH_PROMPT = "🔍 Введіть частину імені або телефону:"
MSG_RECIPIENTS_SEARCH_EMPTY = "Одержувачів за вашим запитом не знайдено."
MSG_RECIPIENTS_TRUNCATED = "Показано {shown} з {total} одержувачів."
MSG_RECIPIENT_DELETE_CONFIRM = "🗑 Видалити одержувача?"
MSG_RECIPIENT_DELETED = "✅ Одержувача видалено."
MSG_RECIPIENT_UPDATED = "✅ Дані одержувача оновлено."
MSG_RECIPIENT_ASK_COD = "💰 Введіть накладений платіж:"
MSG_RECIPIENT_EDIT_NAME = "👤 Введіть нове ПІБ:"
MSG_RECIPIENT_EDIT_PHONE = "📞 Введіть новий телефон:"
MSG_RECIPIENT_EDIT_CITY = "🏙️ Введіть нове місто:"
MSG_RECIPIENT_EDIT_WAREHOUSE = "🏤 Введіть новий номер відділення:"
MSG_RECIPIENT_INVALID_PHONE = "❌ Невірний формат телефону.\n\nПриклад:\n0671234567"
MSG_RECIPIENT_INVALID_COD = "❌ Невірна сума накладеного платежу.\n\nВведіть число більше 0."

DEFAULT_MONTHLY_COD_LIMIT = 30_000

MSG_SETTINGS_HEADER = "⚙️ Налаштування"
MSG_SETTINGS_AUTO_SWITCH = "🔄 Автоматичне перемикання акаунтів"
MSG_SETTINGS_AUTO_SWITCH_ON = "🟢 Увімкнено"
MSG_SETTINGS_AUTO_SWITCH_OFF = "⚪️ Вимкнено"
BTN_SETTINGS_TOGGLE_AUTO_SWITCH = "🔄 Автоматичне перемикання"

CALLBACK_SETTINGS_TOGGLE_AUTO_SWITCH = "settings:toggle_auto_switch"

BTN_ACCOUNT_SEL_CREATE_ANYWAY = "⚠️ Створити на поточному акаунті"
BTN_ACCOUNT_SEL_SELECT = "🔑 Обрати інший акаунт"
BTN_ACCOUNT_SEL_CANCEL = "❌ Скасувати"

CALLBACK_ACCOUNT_SEL_CREATE_ANYWAY = "account_sel:create_anyway"
CALLBACK_ACCOUNT_SEL_SELECT = "account_sel:select"
CALLBACK_ACCOUNT_SEL_CANCEL = "account_sel:cancel"
CALLBACK_ACCOUNT_SEL_PICK = "account_sel:pick"

MSG_ACCOUNT_AUTO_SWITCHED = (
    "🔄 Активний акаунт змінено автоматично.\n\n"
    "Було:\n"
    "{previous_name}\n\n"
    "Стало:\n"
    "{current_name}\n\n"
    "Причина:\n\n"
    "Поточний акаунт перевищить місячний ліміт."
)
MSG_ACCOUNT_LIMIT_EXCEEDED = (
    "❌ Жоден акаунт Нової Пошти не має достатнього залишку ліміту.\n\n"
    "Потрібно:\n"
    "{required}\n\n"
    "Доступно:\n\n"
    "{available}"
)
MSG_ACCOUNT_LIMIT_WARNING = (
    "⚠️ Поточний акаунт перевищить місячний ліміт.\n\n"
    "Потрібно:\n"
    "{required}\n\n"
    "Доступно:\n\n"
    "{available}"
)
MSG_ACCOUNT_SELECT_HEADER = "🏢 Оберіть акаунт Нової Пошти:"
MSG_ACCOUNT_SELECTED_ACTIVE = "✅ Активний акаунт:\n{account_name}"
MSG_TTN_CANCELLED = "❌ Створення ТТН скасовано."
MSG_ACTION_CANCELLED = "❌ Скасовано."
MSG_MAIN_MENU = "🏠 Головне меню:"

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

BTN_CARD_SELECT = "▶️ Обрати"
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

MSG_CARDS_EMPTY = "💳 Список карток порожній."
MSG_CARDS_LIST_HEADER = "💳 Картки:"
MSG_CARDS_FOOTER = "Керування картками:"
MSG_CARD_ASK_NAME = "💳 Введіть назву картки:"
MSG_CARD_ASK_OWNER = "👤 Введіть ім'я власника картки:"
MSG_CARD_ASK_NUMBER = "💳 Введіть номер картки:"
MSG_CARD_INVALID_NUMBER = "❌ Невірний номер картки.\n\nВведіть рівно 16 цифр."
MSG_CARD_SAVED = "✅ Картку збережено."
MSG_CARD_ACTIVE_CHANGED = "✅ Активну картку змінено."
MSG_CARD_DELETE_CONFIRM = "🗑 Видалити картку?"
MSG_CARD_DELETED = "✅ Картку видалено."
MSG_CARD_EDIT_NAME = "💳 Введіть назву картки:"
MSG_CARD_EDIT_OWNER = "👤 Введіть ім'я власника картки:"
MSG_CARD_EDIT_NUMBER = "💳 Введіть номер картки:"
MSG_CARD_UPDATED = "✅ Дані картки оновлено."
MSG_NO_ACTIVE_PAYMENT_CARD = "❌ Спочатку додайте картку у розділі 💳 Картки."

BTN_NP_ACCOUNT_ACTIVATE = "✅ Зробити активним"
BTN_NP_ACCOUNT_RENAME = "✏️ Перейменувати"
BTN_NP_ACCOUNT_CHANGE_API = "🔑 Змінити API"
BTN_NP_ACCOUNT_DELETE = "🗑 Видалити"
BTN_NP_ACCOUNT_OPEN = "▶️ Відкрити"
BTN_NP_ACCOUNT_ADD = "➕ Додати акаунт"
BTN_NP_ACCOUNT_DELETE_YES = "✅ Так"
BTN_NP_ACCOUNT_DELETE_NO = "❌ Ні"

CALLBACK_NP_ACCOUNT_OPEN = "np_account:open"
CALLBACK_NP_ACCOUNT_ACTIVATE = "np_account:activate"
CALLBACK_NP_ACCOUNT_RENAME = "np_account:rename"
CALLBACK_NP_ACCOUNT_CHANGE_API = "np_account:change_api"
CALLBACK_NP_ACCOUNT_DELETE = "np_account:delete"
CALLBACK_NP_ACCOUNT_DELETE_YES = "np_account:delete:yes"
CALLBACK_NP_ACCOUNT_DELETE_NO = "np_account:delete:no"
CALLBACK_NP_ACCOUNT_ADD = "np_account:add"
CALLBACK_NP_ACCOUNT_BACK = "np_account:back"
CALLBACK_NP_ACCOUNT_DETAIL_BACK = "np_account:detail_back"

MSG_NP_ACCOUNTS_EMPTY = "🏢 Список акаунтів НП порожній."
MSG_NP_ACCOUNTS_LIST_HEADER = "🏢 Акаунти НП:"
MSG_NP_ACCOUNTS_FOOTER = "🏢 Керування акаунтами НП:"
MSG_NP_ACCOUNT_DETAIL_HEADER = "🏢 Акаунт НП:"
MSG_NP_ASK_ACCOUNT_NAME = "🏢 Введіть назву акаунта:"
MSG_NP_ASK_API_KEY = "🔑 Введіть API ключ:"
MSG_NP_ACCOUNT_SAVED = "✅ Акаунт НП збережено."
MSG_NP_ACCOUNT_ACTIVE_CHANGED = "✅ Активний акаунт змінено."
MSG_NP_ACCOUNT_DELETE_CONFIRM = "🗑 Видалити акаунт НП?"
MSG_NP_ACCOUNT_DELETED = "✅ Акаунт НП видалено."
MSG_NP_ACCOUNT_RENAMED = "✅ Назву акаунта оновлено."
MSG_NP_ACCOUNT_API_UPDATED = "✅ API ключ акаунта оновлено."
MSG_NO_ACTIVE_NP_ACCOUNT = "❌ Не налаштовано жодного акаунта Нової Пошти."

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
    "📦 Надішліть дані одним повідомленням:\n\n"
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
    "❌ Невірний формат.\n\n"
    "Надішліть рівно 5 непорожніх рядків.\n\n"
    "Приклад:\n\n"
    "Іван Петренко\n"
    "0671234567\n"
    "Криве Озеро\n"
    "1\n"
    "1200"
)
MSG_TTN_NO_CITIES = "❌ Населений пункт не знайдено.\n\nСпробуйте інший запит."
MSG_TTN_NO_WAREHOUSES = "❌ Відділення не знайдено.\n\nСпробуйте інший запит."
MSG_TTN_CREATING = "⏳ Створюємо ТТН..."
MSG_TTN_ASK_PRODUCTS = (
    "📦 Введіть товари одним повідомленням.\n\n"
    "Кожен товар — з нового рядка.\n\n"
    "Приклад:\n\n"
    "Палетка 001\n"
    "Блиск 009\n"
    "Туш 005"
)
MSG_TTN_INVALID_PRODUCTS = (
    "❌ Додайте хоча б один товар.\n\n"
    "Кожен товар — з нового рядка."
)
MSG_ORDER_ITEMS_UPDATED = "✅ Список товарів оновлено."
BTN_WAYBILL_EDIT_PRODUCTS = "✏️ Редагувати товари"
CALLBACK_WAYBILL_EDIT_PRODUCTS = "waybill:edit_products"
MSG_TTN_PRINT_LINK = "📄 PDF:\n{link}"
MSG_TTN_CREATE_FAILED = "❌ Не вдалося створити ТТН:\n\n{error}"
MSG_TTN_SENDER_NOT_CONFIGURED = (
    "❌ Відправника не налаштовано.\n\n{error}\n\n"
    "Зверніться до адміністратора."
)
