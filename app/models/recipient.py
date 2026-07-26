from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Recipient(Base):
    """Saved TTN recipient for a Telegram user."""

    __tablename__ = "recipients"
    __table_args__ = (
        UniqueConstraint("telegram_user_id", "phone", name="uq_recipients_user_phone"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        index=True,
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    city_name: Mapped[str] = mapped_column(String(255), nullable=False)
    city_ref: Mapped[str] = mapped_column(String(36), nullable=False)
    warehouse_number: Mapped[str] = mapped_column(String(32), nullable=False)
    warehouse_ref: Mapped[str] = mapped_column(String(36), nullable=False)
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
