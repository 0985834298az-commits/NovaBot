"""Data access repositories."""

from app.repositories.recipient_repository import RecipientRepository
from app.repositories.user_repository import UserRepository

__all__ = ("RecipientRepository", "UserRepository")
