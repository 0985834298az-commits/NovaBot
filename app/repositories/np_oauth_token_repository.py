"""Persistence for encrypted Nova Poshta OAuth tokens."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.np_oauth_token import NpOAuthToken


class NpOAuthTokenRepository:
    """CRUD for np_oauth_tokens."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_user_id(
        self,
        telegram_user_id: int,
    ) -> NpOAuthToken | None:
        result = await self._session.execute(
            select(NpOAuthToken).where(
                NpOAuthToken.telegram_user_id == telegram_user_id,
            ),
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        telegram_user_id: int,
        access_token_enc: str,
        refresh_token_enc: str,
        id_token_enc: str,
        expires_at: datetime,
        scope: str,
        token_type: str,
    ) -> NpOAuthToken:
        row = await self.get_by_telegram_user_id(telegram_user_id)
        if row is None:
            row = NpOAuthToken(
                telegram_user_id=telegram_user_id,
                access_token_enc=access_token_enc,
                refresh_token_enc=refresh_token_enc,
                id_token_enc=id_token_enc,
                expires_at=expires_at,
                scope=scope,
                token_type=token_type,
            )
            self._session.add(row)
        else:
            row.access_token_enc = access_token_enc
            row.refresh_token_enc = refresh_token_enc
            row.id_token_enc = id_token_enc
            row.expires_at = expires_at
            row.scope = scope
            row.token_type = token_type
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def delete_by_telegram_user_id(self, telegram_user_id: int) -> bool:
        row = await self.get_by_telegram_user_id(telegram_user_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True
