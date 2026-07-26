from __future__ import annotations

import asyncio
import json
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientTimeout
from loguru import logger

from app.nova_poshta.constants import (
    API_URL,
    DEFAULT_TIMEOUT_SECONDS,
    METHOD_GET_STATUS,
    MODEL_COMMON,
)
from app.nova_poshta.exceptions import (
    NovaPoshtaError,
    NovaPoshtaResponseError,
    NovaPoshtaTransportError,
)
from app.utils.ssl import create_ssl_context


class NovaPoshtaClient:
    """Async client for the Nova Poshta JSON API."""

    def __init__(
        self,
        api_key: str,
        *,
        session: aiohttp.ClientSession | None = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not api_key.strip():
            msg = "Nova Poshta API key must not be empty."
            raise ValueError(msg)

        self._api_key = api_key.strip()
        self._session = session
        self._owns_session = session is None
        self._timeout = ClientTimeout(total=timeout)

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=create_ssl_context())
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=self._timeout,
                headers={"Content-Type": "application/json"},
            )
            self._owns_session = True

        return self._session

    async def close(self) -> None:
        """Close the underlying HTTP session if owned by this client."""
        if self._owns_session and self._session is not None and not self._session.closed:
            await self._session.close()
            logger.debug("Nova Poshta HTTP session closed")

    async def __aenter__(self) -> NovaPoshtaClient:
        await self._ensure_session()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def _call(
        self,
        model_name: str,
        called_method: str,
        method_properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "apiKey": self._api_key,
            "modelName": model_name,
            "calledMethod": called_method,
            "methodProperties": method_properties or {},
        }

        session = await self._ensure_session()

        logger.debug(
            "Nova Poshta request payload: {}",
            json.dumps(payload, ensure_ascii=False),
        )

        try:
            async with session.post(API_URL, json=payload) as response:
                raw_body = await response.text()
                logger.info(
                    "Nova Poshta raw response (HTTP {}): {}",
                    response.status,
                    raw_body,
                )

                try:
                    data = json.loads(raw_body)
                except json.JSONDecodeError as exc:
                    msg = "Nova Poshta API returned a non-JSON response"
                    logger.error("{}: {}", msg, raw_body[:500])
                    raise NovaPoshtaResponseError(msg) from exc

                if not isinstance(data, dict):
                    msg = "Nova Poshta API returned an unexpected JSON payload"
                    logger.error("{}: {!r}", msg, data)
                    raise NovaPoshtaResponseError(msg)

                if response.status >= 500:
                    msg = f"Nova Poshta API returned HTTP {response.status}"
                    logger.error("{}: {}", msg, raw_body[:500])
                    raise NovaPoshtaTransportError(
                        msg,
                        status_code=response.status,
                    )

                if data.get("success") is True:
                    logger.info(
                        "Nova Poshta request succeeded: model={} method={}",
                        model_name,
                        called_method,
                    )
                else:
                    logger.warning(
                        "Nova Poshta request failed: model={} method={} errors={}",
                        model_name,
                        called_method,
                        data.get("errors"),
                    )

                return data

        except NovaPoshtaError:
            raise
        except asyncio.TimeoutError as exc:
            msg = "Nova Poshta API request timed out"
            logger.error(msg)
            raise NovaPoshtaTransportError(msg) from exc
        except ClientError as exc:
            msg = f"Nova Poshta API request failed: {exc}"
            logger.error(msg)
            raise NovaPoshtaTransportError(msg) from exc

    async def get_status(self) -> dict[str, Any]:
        """
        Call Common/getServiceTypes and return parsed JSON.

        Nova Poshta uses this lightweight reference method to verify API access.
        """
        return await self._call(MODEL_COMMON, METHOD_GET_STATUS)

    async def validate_api_key(self) -> bool:
        """Return True when the configured API key is valid."""
        try:
            response = await self.get_status()
        except NovaPoshtaError:
            logger.warning("Nova Poshta API key validation failed due to transport error")
            return False

        errors = [str(error) for error in response.get("errors") or []]
        if any("API key incorrect" in error for error in errors):
            logger.warning("Nova Poshta API key is invalid: errors={}", errors)
            return False

        is_valid = response.get("success") is True
        if is_valid:
            logger.info("Nova Poshta API key is valid")
        else:
            logger.warning("Nova Poshta API key validation failed: errors={}", errors)

        return is_valid
