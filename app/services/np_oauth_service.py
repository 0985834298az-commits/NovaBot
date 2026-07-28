"""Nova Poshta OAuth token lifecycle: store, load, auto-refresh."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MSG_OAUTH_NOT_CONFIGURED, MSG_OAUTH_REFRESH_FAILED
from app.nova_poshta.exceptions import NovaPoshtaApiError
from app.nova_poshta.oauth_client import (
    OAuthTokenSet,
    needs_refresh,
    refresh_access_token,
)
from app.nova_poshta.oauth_crypto import decrypt_secret, encrypt_secret
from app.repositories.np_oauth_token_repository import NpOAuthTokenRepository


@dataclass(frozen=True, slots=True)
class StoredOAuthTokens:
    """Decrypted OAuth tokens for runtime use."""

    access_token: str
    refresh_token: str
    id_token: str
    expires_at: datetime
    scope: str
    token_type: str


class NpOAuthService:
    """Manage Business Cabinet OAuth tokens for a Telegram user."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = NpOAuthTokenRepository(session)

    async def save_tokens(
        self,
        telegram_user_id: int,
        tokens: OAuthTokenSet,
    ) -> StoredOAuthTokens:
        """Encrypt and persist a fresh token set."""
        await self._repo.upsert(
            telegram_user_id=telegram_user_id,
            access_token_enc=encrypt_secret(tokens.access_token),
            refresh_token_enc=encrypt_secret(tokens.refresh_token),
            id_token_enc=encrypt_secret(tokens.id_token) if tokens.id_token else "",
            expires_at=tokens.expires_at,
            scope=tokens.scope,
            token_type=tokens.token_type,
        )
        await self._session.flush()
        logger.info(
            "Stored NP OAuth tokens for user {} (expires_at={})",
            telegram_user_id,
            tokens.expires_at.isoformat(),
        )
        return StoredOAuthTokens(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            id_token=tokens.id_token,
            expires_at=tokens.expires_at,
            scope=tokens.scope,
            token_type=tokens.token_type,
        )

    async def load_tokens(self, telegram_user_id: int) -> StoredOAuthTokens | None:
        """Load and decrypt stored tokens, or None if missing."""
        row = await self._repo.get_by_telegram_user_id(telegram_user_id)
        if row is None:
            return None
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return StoredOAuthTokens(
            access_token=decrypt_secret(row.access_token_enc),
            refresh_token=decrypt_secret(row.refresh_token_enc),
            id_token=decrypt_secret(row.id_token_enc) if row.id_token_enc else "",
            expires_at=expires_at,
            scope=row.scope,
            token_type=row.token_type,
        )

    async def clear_tokens(self, telegram_user_id: int) -> bool:
        deleted = await self._repo.delete_by_telegram_user_id(telegram_user_id)
        if deleted:
            await self._session.flush()
        return deleted

    async def get_valid_access_token(self, telegram_user_id: int) -> str:
        """
        Return a usable access_token, refreshing automatically when near expiry.

        Raises NovaPoshtaApiError when the user has never completed OAuth login.
        """
        stored = await self.load_tokens(telegram_user_id)
        if stored is None:
            raise NovaPoshtaApiError(MSG_OAUTH_NOT_CONFIGURED)

        if not needs_refresh(stored.expires_at):
            return stored.access_token

        logger.info(
            "Refreshing NP OAuth access_token for user {} (expires_at={})",
            telegram_user_id,
            stored.expires_at.isoformat(),
        )
        try:
            refreshed = await refresh_access_token(stored.refresh_token)
        except ValueError as exc:
            await self.clear_tokens(telegram_user_id)
            raise NovaPoshtaApiError(MSG_OAUTH_REFRESH_FAILED) from exc

        saved = await self.save_tokens(telegram_user_id, refreshed)
        return saved.access_token
