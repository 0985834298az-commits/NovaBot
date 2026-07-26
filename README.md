# NovaBot

Production-ready Telegram bot scaffold built with **Python 3.12**, **aiogram 3.x**, and **SQLAlchemy 2**.

## Features

- Modular architecture (`handlers`, `services`, `models`, etc.)
- Async SQLAlchemy with SQLite (ready for PostgreSQL migration)
- Environment-based configuration via `python-dotenv`
- Structured logging with Loguru
- Admin-only access via `ADMIN_IDS`
- `/start` command handler

## Project structure

```
NovaBot/
├── app/
│   ├── bot/           # Bot lifecycle, middleware, dispatcher setup
│   ├── config/        # Settings and environment variables
│   ├── database/      # SQLAlchemy engine and sessions
│   ├── handlers/      # Telegram update handlers
│   ├── keyboards/     # Reply/inline keyboards
│   ├── models/        # ORM models
│   ├── nova_poshta/   # Nova Poshta integration (placeholder)
│   ├── parser/        # Data parsers (placeholder)
│   ├── services/      # Business logic
│   └── utils/         # Shared utilities
├── data/              # SQLite database files
├── logs/              # Application logs
├── tests/
├── run.py             # Entry point
├── requirements.txt
├── .env.example
└── README.md
```

## Requirements

- Python 3.12+
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

## Quick start

1. **Clone and enter the project**

   ```bash
   cd NovaBot
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate  # Linux/macOS
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**

   ```bash
   copy .env.example .env   # Windows
   # cp .env.example .env   # Linux/macOS
   ```

   Edit `.env` and set your `BOT_TOKEN` and `ADMIN_IDS`.

   `ADMIN_IDS` is a comma-separated list of Telegram user IDs allowed to use the bot.
   You can get your ID from [@userinfobot](https://t.me/userinfobot).

5. **Run the bot**

   ```bash
   python run.py
   ```

   On successful startup you should see:

   ```
   NovaBot v0.2 started successfully
   ```

6. **Test in Telegram**

   Send `/start` to your bot.

   - **Authorized user** (ID in `ADMIN_IDS`):

     ```
     👋 Вітаємо у NovaBot!

     Version: v0.2

     Bot is ready.
     ```

   - **Unauthorized user**:

     ```
     ⛔️ У вас немає доступу до NovaBot.
     ```

## Environment variables

| Variable         | Required | Default                        | Description              |
|------------------|----------|--------------------------------|--------------------------|
| `BOT_TOKEN`      | Yes      | —                              | Telegram bot token       |
| `ADMIN_IDS`      | Yes      | —                              | Comma-separated Telegram user IDs with bot access |
| `DATABASE_URL`   | No       | `sqlite+aiosqlite:///data/novabot.db` | Database connection URL |
| `LOG_LEVEL`      | No       | `INFO`                         | Logging level            |
| `SSL_CA_BUNDLE`  | No       | —                              | Extra PEM file with custom CA certificates |

## SSL on Windows

NovaBot verifies HTTPS certificates (SSL is never disabled).

On Windows, antivirus tools such as Avast can intercept HTTPS traffic and replace site certificates with their own CA. Python's default `certifi` bundle does not include those roots, which causes:

```
TelegramNetworkError: ClientConnectorCertificateError: SSL: CERTIFICATE_VERIFY_FAILED
```

NovaBot fixes this by combining:

- **`truststore`** — uses the Windows certificate store (includes antivirus/corporate roots)
- **`certifi`** — Mozilla CA bundle for public certificate authorities

If you still see SSL errors, export your organization's root CA to a PEM file and set `SSL_CA_BUNDLE` in `.env`.

## PostgreSQL migration

When ready to switch from SQLite to PostgreSQL:

1. Install `asyncpg`:

   ```bash
   pip install asyncpg
   ```

2. Update `DATABASE_URL` in `.env`:

   ```env
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/novabot
   ```

No code changes are required in the database layer.

## Development

- Handlers live in `app/handlers/`
- Add ORM models in `app/models/` and inherit from `app.database.base.Base`
- Business logic goes in `app/services/`
- Nova Poshta integration will be added under `app/nova_poshta/`

## License

MIT
