from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order_item import OrderItem


class OrderItemRepository:
    """Persistence layer for order product lines."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_items(
        self,
        order_id: int,
        product_names: list[str],
    ) -> list[OrderItem]:
        """Create product lines for an order, preserving input order."""
        items: list[OrderItem] = []
        for product_name in product_names:
            item = OrderItem(
                order_id=order_id,
                product_name=product_name.strip(),
            )
            self._session.add(item)
            items.append(item)

        await self._session.flush()
        for item in items:
            await self._session.refresh(item)
        return items

    async def get_by_order_id(self, order_id: int) -> list[OrderItem]:
        """Return product lines for an order in creation order."""
        result = await self._session.execute(
            select(OrderItem)
            .where(OrderItem.order_id == order_id)
            .order_by(OrderItem.id.asc()),
        )
        return list(result.scalars().all())

    async def get_by_order_ids(self, order_ids: list[int]) -> dict[int, list[OrderItem]]:
        """Return product lines grouped by order id."""
        if not order_ids:
            return {}

        result = await self._session.execute(
            select(OrderItem)
            .where(OrderItem.order_id.in_(order_ids))
            .order_by(OrderItem.order_id.asc(), OrderItem.id.asc()),
        )
        grouped: dict[int, list[OrderItem]] = {}
        for item in result.scalars().all():
            grouped.setdefault(item.order_id, []).append(item)
        return grouped

    async def replace_items(
        self,
        order_id: int,
        product_names: list[str],
    ) -> list[OrderItem]:
        """Replace all product lines for an order."""
        await self._session.execute(
            delete(OrderItem).where(OrderItem.order_id == order_id),
        )
        await self._session.flush()
        return await self.create_items(order_id, product_names)
