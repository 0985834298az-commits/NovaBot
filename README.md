# NovaBot

Production-ready Telegram bot scaffold built with **Python 3.12**, **aiogram 3.x**, and **SQLAlchemy 2**.

## Features

- Modular architecture (`handlers`, `services`, `models`, etc.)
- Async SQLAlchemy with SQLite (ready for PostgreSQL migration)
- Environment-based configuration via `python-dotenv`
- Structured logging with Loguru
- `/start` command handler

## Project structure

```
NovaBot/
├── app/
│   ├── bot/           # Bot lifecycle and dispatcher setup
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

   Edit `.env` and set your `BOT_TOKEN`.

5. **Run the bot**

   ```bash
   python run.py
   ```

   On successful startup you should see:

   ```
   NovaBot v0.1 started successfully
   ```

6. **Test in Telegram**

   Send `/start` to your bot. It will reply:

   ```
   NovaBot v0.1 started successfully
   ```

## Environment variables

| Variable       | Required | Default                        | Description              |
|----------------|----------|--------------------------------|--------------------------|
| `BOT_TOKEN`    | Yes      | —                              | Telegram bot token       |
| `DATABASE_URL` | No       | `sqlite+aiosqlite:///data/novabot.db` | Database connection URL |
| `LOG_LEVEL`    | No       | `INFO`                         | Logging level            |

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
