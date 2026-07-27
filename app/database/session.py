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


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session and close it after use."""
    async with session_factory() as session:
        yield session
