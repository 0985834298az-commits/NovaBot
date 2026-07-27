from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

load_dotenv(BASE_DIR / ".env")


def _parse_admin_ids(raw: str) -> frozenset[int]:
    """Parse comma-separated Telegram user IDs from ADMIN_IDS."""
    if not raw.strip():
        msg = "ADMIN_IDS is not set. Add comma-separated Telegram user IDs to .env."
        raise ValueError(msg)

    admin_ids: set[int] = set()
    for part in raw.split(","):
        value = part.strip()
        if not value:
            continue
        try:
            admin_ids.add(int(value))
        except ValueError as exc:
            msg = f"Invalid ADMIN_IDS entry: {value!r}"
            raise ValueError(msg) from exc

    if not admin_ids:
        msg = "ADMIN_IDS must contain at least one Telegram user ID."
        raise ValueError(msg)

    return frozenset(admin_ids)


@dataclass(frozen=True, slots=True)
class Settings:
    """Application settings loaded from environment variables."""

    bot_token: str
    admin_ids: frozenset[int]
    database_url: str
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        bot_token = os.getenv("BOT_TOKEN", "").strip()
        if not bot_token:
            msg = "BOT_TOKEN is not set. Copy .env.example to .env and add your token."
            raise ValueError(msg)

        admin_ids = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))

        default_db_path = (DATA_DIR / "novabot.db").as_posix()
        database_url = os.getenv(
            "DATABASE_URL",
            f"sqlite+aiosqlite:///{default_db_path}",
        )
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()

        return cls(
            bot_token=bot_token,
            admin_ids=admin_ids,
            database_url=database_url,
            log_level=log_level,
        )
