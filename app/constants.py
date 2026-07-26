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

CALLBACK_REPLACE_API_KEY = "replace_api_key"

MSG_CREATE_TTN_SOON = "Створення ТТН скоро буде доступне."
MSG_WAYBILLS_EMPTY = "Історія накладних порожня."
MSG_RECIPIENTS_EMPTY = "Список одержувачів порожній."
MSG_SETTINGS_SOON = "Налаштування скоро будуть доступні."

API_KEY_MASK_SUFFIX = "****"
API_KEY_VISIBLE_CHARS = 8
