from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment_card import PaymentCard
from app.utils.payment_card import mask_card_number


class PaymentCardRepository:
    """Persistence layer for COD payment cards."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_card(
        self,
        *,
        telegram_user_id: int,
        card_name: str,
        card_ref: str,
        owner_name: str,
        card_number: str,
        bank_name: str | None = None,
        masked_number: str | None = None,
        imported_at: datetime | None = None,
    ) -> PaymentCard:
        """Create a payment card; the first card becomes active automatically."""
        existing_cards = await self.get_all_cards(telegram_user_id)
        if masked_number is None:
            masked_number = (
                mask_card_number(card_number)
                if len(card_number) == 16
                else card_number
            )
        card = PaymentCard(
            telegram_user_id=telegram_user_id,
            card_name=card_name.strip(),
            card_ref=card_ref.strip(),
            masked_number=masked_number.strip(),
            owner_name=owner_name.strip(),
            card_number=card_number,
            bank_name=bank_name.strip() if bank_name else None,
            is_active=not existing_cards,
            imported_at=imported_at,
        )
        self._session.add(card)
        await self._session.flush()
        await self._session.refresh(card)
        return card

    async def get_all_cards(self, telegram_user_id: int) -> list[PaymentCard]:
        """Return all payment cards for a Telegram user."""
        result = await self._session.execute(
            select(PaymentCard)
            .where(PaymentCard.telegram_user_id == telegram_user_id)
            .order_by(PaymentCard.is_active.desc(), PaymentCard.id.asc()),
        )
        return list(result.scalars().all())

    async def get_by_id(
        self,
        card_id: int,
        telegram_user_id: int,
    ) -> PaymentCard | None:
        """Return a payment card owned by the Telegram user."""
        result = await self._session.execute(
            select(PaymentCard).where(
                PaymentCard.id == card_id,
                PaymentCard.telegram_user_id == telegram_user_id,
            ),
        )
        return result.scalar_one_or_none()

    async def get_by_ref(
        self,
        telegram_user_id: int,
        card_ref: str,
    ) -> PaymentCard | None:
        """Return a payment card matched by Nova Poshta Ref."""
        normalized_ref = card_ref.strip()
        if not normalized_ref:
            return None

        result = await self._session.execute(
            select(PaymentCard).where(
                PaymentCard.telegram_user_id == telegram_user_id,
                PaymentCard.card_ref == normalized_ref,
            ),
        )
        return result.scalar_one_or_none()

    async def get_by_card_number(
        self,
        telegram_user_id: int,
        card_number: str,
    ) -> PaymentCard | None:
        """Return a payment card matched by full card number."""
        if len(card_number) != 16:
            return None

        result = await self._session.execute(
            select(PaymentCard).where(
                PaymentCard.telegram_user_id == telegram_user_id,
                PaymentCard.card_number == card_number,
            ),
        )
        return result.scalar_one_or_none()

    async def upsert_imported_card(
        self,
        *,
        telegram_user_id: int,
        card_name: str,
        card_ref: str,
        masked_number: str,
        owner_name: str,
        card_number: str,
        imported_at: datetime,
    ) -> PaymentCard:
        """Create or update a card imported from Nova Poshta."""
        existing = await self.get_by_ref(telegram_user_id, card_ref)
        if existing is None and len(card_number) == 16:
            existing = await self.get_by_card_number(telegram_user_id, card_number)

        if existing is not None:
            existing.card_name = card_name.strip()
            existing.card_ref = card_ref.strip()
            existing.masked_number = masked_number.strip()
            existing.owner_name = owner_name.strip()
            if len(card_number) == 16:
                existing.card_number = card_number
            existing.imported_at = imported_at
            await self._session.flush()
            await self._session.refresh(existing)
            return existing

        existing_cards = await self.get_all_cards(telegram_user_id)
        card = PaymentCard(
            telegram_user_id=telegram_user_id,
            card_name=card_name.strip(),
            card_ref=card_ref.strip(),
            masked_number=masked_number.strip(),
            owner_name=owner_name.strip(),
            card_number=card_number if len(card_number) == 16 else "",
            is_active=not existing_cards,
            imported_at=imported_at,
        )
        self._session.add(card)
        await self._session.flush()
        await self._session.refresh(card)
        return card

    async def get_active_card(self, telegram_user_id: int) -> PaymentCard | None:
        """Return the active payment card for a Telegram user."""
        result = await self._session.execute(
            select(PaymentCard).where(
                PaymentCard.telegram_user_id == telegram_user_id,
                PaymentCard.is_active.is_(True),
            ),
        )
        return result.scalar_one_or_none()

    async def set_active_card(
        self,
        card_id: int,
        telegram_user_id: int,
    ) -> PaymentCard | None:
        """Deactivate other cards and mark the selected card as active."""
        card = await self.get_by_id(card_id, telegram_user_id)
        if card is None:
            return None

        await self._session.execute(
            update(PaymentCard)
            .where(PaymentCard.telegram_user_id == telegram_user_id)
            .values(is_active=False),
        )
        card.is_active = True
        await self._session.flush()
        await self._session.refresh(card)
        return card

    async def update_card(
        self,
        card_id: int,
        telegram_user_id: int,
        *,
        card_name: str,
        card_ref: str,
        owner_name: str,
        card_number: str,
        bank_name: str | None = None,
        masked_number: str | None = None,
    ) -> PaymentCard | None:
        """Update card name, owner name, card number, and optional Nova Poshta Ref."""
        card = await self.get_by_id(card_id, telegram_user_id)
        if card is None:
            return None

        card.card_name = card_name.strip()
        card.card_ref = card_ref.strip()
        card.owner_name = owner_name.strip()
        card.card_number = card_number
        if masked_number is not None:
            card.masked_number = masked_number.strip()
        elif len(card_number) == 16:
            card.masked_number = mask_card_number(card_number)
        if bank_name is not None:
            card.bank_name = bank_name.strip() or None

        await self._session.flush()
        await self._session.refresh(card)
        return card

    async def update_card_ref(
        self,
        card: PaymentCard,
        *,
        card_ref: str,
    ) -> PaymentCard:
        """Update only the Nova Poshta card Ref."""
        card.card_ref = card_ref.strip()
        await self._session.flush()
        await self._session.refresh(card)
        return card

    async def delete_card(self, card_id: int, telegram_user_id: int) -> bool:
        """Delete a payment card and activate another one when needed."""
        card = await self.get_by_id(card_id, telegram_user_id)
        if card is None:
            return False

        was_active = card.is_active
        await self._session.delete(card)
        await self._session.flush()

        if was_active:
            remaining_cards = await self.get_all_cards(telegram_user_id)
            if remaining_cards:
                await self.set_active_card(remaining_cards[0].id, telegram_user_id)

        return True
