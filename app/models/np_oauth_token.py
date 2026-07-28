"""Persisted Nova Poshta OAuth tokens (encrypted at rest)."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class NpOAuthToken(Base):
    """OAuth tokens for Business Cabinet API access (per Telegram user)."""

    __tablename__ = "np_oauth_tokens"
    __table_args__ = (
        UniqueConstraint("telegram_user_id", name="uq_np_oauth_tokens_telegram_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        index=True,
        nullable=False,
    )
    access_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    id_token_enc: Mapped[str] = mapped_column(Text, default="", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scope: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    token_type: Mapped[str] = mapped_column(String(64), default="bearer", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
