from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import DATA_DIR
from app.database.base import Base


def create_engine(database_url: str) -> AsyncEngine:
    """Create an async SQLAlchemy engine."""
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_async_engine(
        database_url,
        echo=False,
        connect_args=connect_args,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the engine."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def init_db(engine: AsyncEngine) -> None:
    """Create database tables if they do not exist."""
    import app.models  # noqa: F401

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_migrate_payment_cards)
        await connection.run_sync(_migrate_nova_poshta_accounts)
        await connection.run_sync(_migrate_users)
        await connection.run_sync(_migrate_waybills)


def _migrate_nova_poshta_accounts(connection) -> None:
    """Add monthly COD limit to Nova Poshta accounts."""
    from sqlalchemy import inspect, text

    from app.constants import DEFAULT_MONTHLY_COD_LIMIT

    inspector = inspect(connection)
    if "nova_poshta_accounts" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("nova_poshta_accounts")}
    if "monthly_limit" not in columns:
        connection.execute(
            text(
                "ALTER TABLE nova_poshta_accounts "
                f"ADD COLUMN monthly_limit INTEGER DEFAULT {DEFAULT_MONTHLY_COD_LIMIT}",
            ),
        )


def _migrate_users(connection) -> None:
    """Add user settings columns."""
    from sqlalchemy import inspect, text

    inspector = inspect(connection)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "auto_account_switching" not in columns:
        connection.execute(
            text(
                "ALTER TABLE users "
                "ADD COLUMN auto_account_switching BOOLEAN DEFAULT 1",
            ),
        )


def _migrate_waybills(connection) -> None:
    """Add Nova Poshta account reference to waybills."""
    from sqlalchemy import inspect, text

    inspector = inspect(connection)
    if "waybills" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("waybills")}
    if "nova_poshta_account_id" not in columns:
        connection.execute(
            text("ALTER TABLE waybills ADD COLUMN nova_poshta_account_id BIGINT"),
        )
    columns = {column["name"] for column in inspector.get_columns("waybills")}
    if "is_deleted" not in columns:
        connection.execute(
            text("ALTER TABLE waybills ADD COLUMN is_deleted BOOLEAN DEFAULT 0 NOT NULL"),
        )
        connection.execute(
            text(
                "UPDATE waybills "
                "SET is_deleted = 1 "
                "WHERE shipment_status_code IN ('2', '3')",
            ),
        )


def _migrate_payment_cards(connection) -> None:
    """Add v2 payment card columns to existing SQLite databases."""
    from sqlalchemy import inspect, text

    inspector = inspect(connection)
    if "payment_cards" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("payment_cards")}
    if "card_name" not in columns:
        connection.execute(
            text("ALTER TABLE payment_cards ADD COLUMN card_name VARCHAR(255) DEFAULT ''"),
        )
        connection.execute(
            text(
                "UPDATE payment_cards "
                "SET card_name = owner_name "
                "WHERE card_name IS NULL OR card_name = ''",
            ),
        )
    columns = {column["name"] for column in inspector.get_columns("payment_cards")}
    if "card_ref" not in columns:
        connection.execute(
            text("ALTER TABLE payment_cards ADD COLUMN card_ref VARCHAR(36) DEFAULT ''"),
        )
    columns = {column["name"] for column in inspector.get_columns("payment_cards")}
    if "masked_number" not in columns:
        connection.execute(
            text("ALTER TABLE payment_cards ADD COLUMN masked_number VARCHAR(32) DEFAULT ''"),
        )
        connection.execute(
            text(
                "UPDATE payment_cards "
                "SET masked_number = SUBSTR(card_number, 1, 4) || ' ** ** ' || SUBSTR(card_number, -4) "
                "WHERE length(card_number) = 16 "
                "AND (masked_number IS NULL OR masked_number = '')",
            ),
        )
    columns = {column["name"] for column in inspector.get_columns("payment_cards")}
    if "imported_at" not in columns:
        connection.execute(
            text("ALTER TABLE payment_cards ADD COLUMN imported_at DATETIME"),
        )
    columns = {column["name"] for column in inspector.get_columns("payment_cards")}
    if "nova_poshta_account_id" not in columns:
        connection.execute(
            text("ALTER TABLE payment_cards ADD COLUMN nova_poshta_account_id BIGINT"),
        )
        cards = connection.execute(
            text("SELECT id, telegram_user_id FROM payment_cards"),
        ).fetchall()
        for card_id, telegram_user_id in cards:
            account_row = connection.execute(
                text(
                    "SELECT id FROM nova_poshta_accounts "
                    "WHERE telegram_user_id = :telegram_user_id "
                    "AND is_active = 1 "
                    "ORDER BY id ASC LIMIT 1",
                ),
                {"telegram_user_id": telegram_user_id},
            ).fetchone()
            if account_row is None:
                account_row = connection.execute(
                    text(
                        "SELECT id FROM nova_poshta_accounts "
                        "WHERE telegram_user_id = :telegram_user_id "
                        "ORDER BY id ASC LIMIT 1",
                    ),
                    {"telegram_user_id": telegram_user_id},
                ).fetchone()
            if account_row is None:
                connection.execute(
                    text("DELETE FROM payment_cards WHERE id = :card_id"),
                    {"card_id": card_id},
                )
                continue
            connection.execute(
                text(
                    "UPDATE payment_cards "
                    "SET nova_poshta_account_id = :account_id "
                    "WHERE id = :card_id",
                ),
                {"account_id": account_row[0], "card_id": card_id},
            )


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session and close it after use."""
    async with session_factory() as session:
        yield session
