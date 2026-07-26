from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recipient import Recipient
from app.services.ttn_service import normalize_phone


class RecipientRepository:
    """Persistence layer for saved TTN recipients."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_recipient(
        self,
        *,
        telegram_user_id: int,
        full_name: str,
        phone: str,
        city_name: str,
        city_ref: str,
        warehouse_number: str,
        warehouse_ref: str,
    ) -> Recipient:
        """Create or update a recipient keyed by Telegram user and phone."""
        normalized_phone = normalize_phone(phone)
        if normalized_phone is None:
            msg = "Invalid recipient phone number"
            raise ValueError(msg)

        recipient = await self.find_by_phone(telegram_user_id, normalized_phone)
        if recipient is None:
            recipient = Recipient(
                telegram_user_id=telegram_user_id,
                phone=normalized_phone,
            )
            self._session.add(recipient)

        recipient.full_name = full_name.strip()
        recipient.phone = normalized_phone
        recipient.city_name = city_name.strip()
        recipient.city_ref = city_ref
        recipient.warehouse_number = warehouse_number.strip().lstrip("№")
        recipient.warehouse_ref = warehouse_ref

        await self._session.flush()
        await self._session.refresh(recipient)
        return recipient

    async def get_all(self, telegram_user_id: int) -> list[Recipient]:
        """Return all recipients for a Telegram user."""
        result = await self._session.execute(
            select(Recipient)
            .where(Recipient.telegram_user_id == telegram_user_id)
            .order_by(Recipient.full_name.asc(), Recipient.id.asc()),
        )
        return list(result.scalars().all())

    async def get_by_id(
        self,
        recipient_id: int,
        telegram_user_id: int,
    ) -> Recipient | None:
        """Return a recipient owned by the Telegram user."""
        result = await self._session.execute(
            select(Recipient).where(
                Recipient.id == recipient_id,
                Recipient.telegram_user_id == telegram_user_id,
            ),
        )
        return result.scalar_one_or_none()

    async def find_by_phone(
        self,
        telegram_user_id: int,
        phone: str,
    ) -> Recipient | None:
        """Find a recipient by normalized phone number."""
        normalized_phone = normalize_phone(phone)
        if normalized_phone is None:
            return None

        result = await self._session.execute(
            select(Recipient).where(
                Recipient.telegram_user_id == telegram_user_id,
                Recipient.phone == normalized_phone,
            ),
        )
        return result.scalar_one_or_none()

    async def find_by_name(
        self,
        telegram_user_id: int,
        name_part: str,
    ) -> list[Recipient]:
        """Find recipients whose name contains the query."""
        query = name_part.strip()
        if not query:
            return []

        result = await self._session.execute(
            select(Recipient)
            .where(
                Recipient.telegram_user_id == telegram_user_id,
                Recipient.full_name.ilike(f"%{query}%"),
            )
            .order_by(Recipient.full_name.asc(), Recipient.id.asc()),
        )
        return list(result.scalars().all())

    async def search(
        self,
        telegram_user_id: int,
        query: str,
    ) -> list[Recipient]:
        """Search recipients by partial name or phone."""
        normalized_query = query.strip()
        if not normalized_query:
            return []

        digits = "".join(char for char in normalized_query if char.isdigit())
        conditions = [Recipient.full_name.ilike(f"%{normalized_query}%")]
        if digits:
            conditions.append(Recipient.phone.ilike(f"%{digits}%"))

        result = await self._session.execute(
            select(Recipient)
            .where(
                Recipient.telegram_user_id == telegram_user_id,
                or_(*conditions),
            )
            .order_by(Recipient.full_name.asc(), Recipient.id.asc()),
        )
        return list(result.scalars().all())

    async def delete(self, recipient_id: int, telegram_user_id: int) -> bool:
        """Delete a recipient owned by the Telegram user."""
        recipient = await self.get_by_id(recipient_id, telegram_user_id)
        if recipient is None:
            return False

        await self._session.delete(recipient)
        await self._session.flush()
        return True
