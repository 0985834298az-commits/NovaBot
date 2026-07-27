from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Waybill(Base):
    """Saved TTN (waybill) for a Telegram user."""

    __tablename__ = "waybills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        index=True,
        nullable=False,
    )
    ttn_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    document_ref: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    recipient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    city_name: Mapped[str] = mapped_column(String(255), nullable=False)
    city_ref: Mapped[str] = mapped_column(String(36), nullable=False)
    warehouse_number: Mapped[str] = mapped_column(String(32), nullable=False)
    warehouse_ref: Mapped[str] = mapped_column(String(36), nullable=False)
    cod_amount: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    delivery_cost: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cargo_description: Mapped[str] = mapped_column(String(255), nullable=False)
    weight: Mapped[str] = mapped_column(String(16), nullable=False)
    declared_cost: Mapped[str] = mapped_column(String(32), nullable=False)
    shipment_status: Mapped[str] = mapped_column(String(255), nullable=False)
    shipment_status_code: Mapped[str] = mapped_column(String(16), nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
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
