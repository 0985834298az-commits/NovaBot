from datetime import datetime

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment_card import PaymentCard
from app.utils.payment_card import mask_card_number


class PaymentCardRepository:
    """Persistence layer for COD payment cards scoped to Nova Poshta accounts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _log_account_context(
        *,
        stage: str,
        telegram_user_id: int,
        nova_poshta_account_id: int,
        nova_poshta_account_name: str | None = None,
        card: PaymentCard | None = None,
    ) -> None:
        logger.info(
            "payment_cards {}: user_id={} current_account_id={} current_account_name={} "
            "card_account_id={} active_account_id={}",
            stage,
            telegram_user_id,
            nova_poshta_account_id,
            nova_poshta_account_name or "unknown",
            card.nova_poshta_account_id if card is not None else None,
            nova_poshta_account_id,
        )

    @staticmethod
    def _log_cards_snapshot(
        *,
        stage: str,
        telegram_user_id: int,
        nova_poshta_account_id: int,
        nova_poshta_account_name: str | None,
        cards: list[PaymentCard],
    ) -> None:
        active = next((card for card in cards if card.is_active), None)
        logger.info(
            "payment_cards {}: user_id={} current_account_id={} current_account_name={} "
            "total={} ids={} card_account_ids={} active_id={} active_account_id={}",
            stage,
            telegram_user_id,
            nova_poshta_account_id,
            nova_poshta_account_name or "unknown",
            len(cards),
            [card.id for card in cards],
            [card.nova_poshta_account_id for card in cards],
            active.id if active else None,
            nova_poshta_account_id,
        )

    async def create_card(
        self,
        *,
        telegram_user_id: int,
        nova_poshta_account_id: int,
        card_name: str,
        card_ref: str,
        owner_name: str,
        card_number: str,
        bank_name: str | None = None,
        masked_number: str | None = None,
        imported_at: datetime | None = None,
        nova_poshta_account_name: str | None = None,
    ) -> PaymentCard:
        """Create a payment card; the first card in the account becomes active."""
        self._log_account_context(
            stage="create_card before",
            telegram_user_id=telegram_user_id,
            nova_poshta_account_id=nova_poshta_account_id,
            nova_poshta_account_name=nova_poshta_account_name,
        )
        existing_cards = await self.get_all_cards(
            telegram_user_id,
            nova_poshta_account_id=nova_poshta_account_id,
            nova_poshta_account_name=nova_poshta_account_name,
        )
        if masked_number is None:
            masked_number = (
                mask_card_number(card_number)
                if len(card_number) == 16
                else card_number
            )
        card = PaymentCard(
            telegram_user_id=telegram_user_id,
            nova_poshta_account_id=nova_poshta_account_id,
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
        self._log_account_context(
            stage="create_card after",
            telegram_user_id=telegram_user_id,
            nova_poshta_account_id=nova_poshta_account_id,
            nova_poshta_account_name=nova_poshta_account_name,
            card=card,
        )
        return card

    async def get_all_cards(
        self,
        telegram_user_id: int,
        *,
        nova_poshta_account_id: int,
        nova_poshta_account_name: str | None = None,
    ) -> list[PaymentCard]:
        """Return all payment cards for a Telegram user and Nova Poshta account."""
        self._log_account_context(
            stage="get_all_cards before",
            telegram_user_id=telegram_user_id,
            nova_poshta_account_id=nova_poshta_account_id,
            nova_poshta_account_name=nova_poshta_account_name,
        )
        result = await self._session.execute(
            select(PaymentCard)
            .where(
                PaymentCard.telegram_user_id == telegram_user_id,
                PaymentCard.nova_poshta_account_id == nova_poshta_account_id,
            )
            .order_by(PaymentCard.is_active.desc(), PaymentCard.id.asc()),
        )
        cards = list(result.scalars().all())
        logger.info(
            "get_all_cards after: user_id={} current_account_id={} count={} card_account_ids={}",
            telegram_user_id,
            nova_poshta_account_id,
            len(cards),
            [card.nova_poshta_account_id for card in cards],
        )
        return cards

    async def get_by_id(
        self,
        card_id: int,
        telegram_user_id: int,
        *,
        nova_poshta_account_id: int,
        nova_poshta_account_name: str | None = None,
    ) -> PaymentCard | None:
        """Return a payment card owned by the Telegram user within an account."""
        self._log_account_context(
            stage="get_by_id before",
            telegram_user_id=telegram_user_id,
            nova_poshta_account_id=nova_poshta_account_id,
            nova_poshta_account_name=nova_poshta_account_name,
        )
        result = await self._session.execute(
            select(PaymentCard).where(
                PaymentCard.id == card_id,
                PaymentCard.telegram_user_id == telegram_user_id,
                PaymentCard.nova_poshta_account_id == nova_poshta_account_id,
            ),
        )
        card = result.scalar_one_or_none()
        self._log_account_context(
            stage="get_by_id after",
            telegram_user_id=telegram_user_id,
            nova_poshta_account_id=nova_poshta_account_id,
            nova_poshta_account_name=nova_poshta_account_name,
            card=card,
        )
        return card

    async def get_by_card_number(
        self,
        telegram_user_id: int,
        nova_poshta_account_id: int,
        card_number: str,
    ) -> PaymentCard | None:
        """Return a payment card matched by full card number within an account."""
        if len(card_number) != 16:
            return None

        result = await self._session.execute(
            select(PaymentCard).where(
                PaymentCard.telegram_user_id == telegram_user_id,
                PaymentCard.nova_poshta_account_id == nova_poshta_account_id,
                PaymentCard.card_number == card_number,
            ),
        )
        return result.scalar_one_or_none()

    async def get_active_card(
        self,
        telegram_user_id: int,
        *,
        nova_poshta_account_id: int,
        nova_poshta_account_name: str | None = None,
    ) -> PaymentCard | None:
        """Return the active payment card for a Telegram user within an account."""
        self._log_account_context(
            stage="get_active_card before",
            telegram_user_id=telegram_user_id,
            nova_poshta_account_id=nova_poshta_account_id,
            nova_poshta_account_name=nova_poshta_account_name,
        )
        result = await self._session.execute(
            select(PaymentCard).where(
                PaymentCard.telegram_user_id == telegram_user_id,
                PaymentCard.nova_poshta_account_id == nova_poshta_account_id,
                PaymentCard.is_active.is_(True),
            ),
        )
        card = result.scalar_one_or_none()
        self._log_account_context(
            stage="get_active_card after",
            telegram_user_id=telegram_user_id,
            nova_poshta_account_id=nova_poshta_account_id,
            nova_poshta_account_name=nova_poshta_account_name,
            card=card,
        )
        return card

    async def set_active_card(
        self,
        card_id: int,
        telegram_user_id: int,
        *,
        nova_poshta_account_id: int,
        nova_poshta_account_name: str | None = None,
    ) -> PaymentCard | None:
        """Deactivate other cards in the account and mark the selected card as active."""
        cards_before = await self.get_all_cards(
            telegram_user_id,
            nova_poshta_account_id=nova_poshta_account_id,
            nova_poshta_account_name=nova_poshta_account_name,
        )
        self._log_cards_snapshot(
            stage="set_active_card before",
            telegram_user_id=telegram_user_id,
            nova_poshta_account_id=nova_poshta_account_id,
            nova_poshta_account_name=nova_poshta_account_name,
            cards=cards_before,
        )

        card = await self.get_by_id(
            card_id,
            telegram_user_id,
            nova_poshta_account_id=nova_poshta_account_id,
            nova_poshta_account_name=nova_poshta_account_name,
        )
        if card is None:
            return None

        await self._session.execute(
            update(PaymentCard)
            .where(
                PaymentCard.telegram_user_id == telegram_user_id,
                PaymentCard.nova_poshta_account_id == nova_poshta_account_id,
            )
            .values(is_active=False),
        )
        card.is_active = True
        await self._session.flush()
        await self._session.refresh(card)

        cards_after = await self.get_all_cards(
            telegram_user_id,
            nova_poshta_account_id=nova_poshta_account_id,
            nova_poshta_account_name=nova_poshta_account_name,
        )
        self._log_cards_snapshot(
            stage="set_active_card after",
            telegram_user_id=telegram_user_id,
            nova_poshta_account_id=nova_poshta_account_id,
            nova_poshta_account_name=nova_poshta_account_name,
            cards=cards_after,
        )
        return card

    async def update_card(
        self,
        card_id: int,
        telegram_user_id: int,
        *,
        nova_poshta_account_id: int,
        card_name: str,
        card_ref: str,
        owner_name: str,
        card_number: str,
        bank_name: str | None = None,
        masked_number: str | None = None,
        nova_poshta_account_name: str | None = None,
    ) -> PaymentCard | None:
        """Update card fields within a Nova Poshta account."""
        card = await self.get_by_id(
            card_id,
            telegram_user_id,
            nova_poshta_account_id=nova_poshta_account_id,
            nova_poshta_account_name=nova_poshta_account_name,
        )
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

    async def delete_card(
        self,
        card_id: int,
        telegram_user_id: int,
        *,
        nova_poshta_account_id: int,
        nova_poshta_account_name: str | None = None,
    ) -> bool:
        """Delete a payment card and activate another one in the same account when needed."""
        card = await self.get_by_id(
            card_id,
            telegram_user_id,
            nova_poshta_account_id=nova_poshta_account_id,
            nova_poshta_account_name=nova_poshta_account_name,
        )
        if card is None:
            return False

        was_active = card.is_active
        await self._session.delete(card)
        await self._session.flush()

        if was_active:
            remaining_cards = await self.get_all_cards(
                telegram_user_id,
                nova_poshta_account_id=nova_poshta_account_id,
                nova_poshta_account_name=nova_poshta_account_name,
            )
            if remaining_cards:
                await self.set_active_card(
                    remaining_cards[0].id,
                    telegram_user_id,
                    nova_poshta_account_id=nova_poshta_account_id,
                    nova_poshta_account_name=nova_poshta_account_name,
                )

        return True
