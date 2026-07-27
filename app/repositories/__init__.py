"""Data access repositories."""

from app.repositories.payment_card_repository import PaymentCardRepository
from app.repositories.recipient_repository import RecipientRepository
from app.repositories.user_repository import UserRepository
from app.repositories.waybill_repository import WaybillRepository

__all__ = (
    "PaymentCardRepository",
    "RecipientRepository",
    "UserRepository",
    "WaybillRepository",
)
