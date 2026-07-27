from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment_card import PaymentCard


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
    ) -> PaymentCard:
        """Create a payment card; the first card becomes active automatically."""
        existing_cards = await self.get_all_cards(telegram_user_id)
        card = PaymentCard(
            telegram_user_id=telegram_user_id,
            card_name=card_name.strip(),
            card_ref=card_ref.strip(),
            owner_name=owner_name.strip(),
            card_number=card_number,
            bank_name=bank_name.strip() if bank_name else None,
            is_active=not existing_cards,
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
    ) -> PaymentCard | None:
        """Update card name, owner name, card number, and Nova Poshta Ref."""
        card = await self.get_by_id(card_id, telegram_user_id)
        if card is None:
            return None

        card.card_name = card_name.strip()
        card.card_ref = card_ref.strip()
        card.owner_name = owner_name.strip()
        card.card_number = card_number
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
