from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True, slots=True)
class Settings:
    """Application settings loaded from environment variables."""

    bot_token: str
    database_url: str
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        bot_token = os.getenv("BOT_TOKEN", "").strip()
        if not bot_token:
            msg = "BOT_TOKEN is not set. Copy .env.example to .env and add your token."
            raise ValueError(msg)

        default_db_path = (DATA_DIR / "novabot.db").as_posix()
        database_url = os.getenv(
            "DATABASE_URL",
            f"sqlite+aiosqlite:///{default_db_path}",
        )
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()

        return cls(
            bot_token=bot_token,
            database_url=database_url,
            log_level=log_level,
        )
