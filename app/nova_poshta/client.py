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
    METHOD_GET_CATALOG_COUNTERPARTY,
    METHOD_GET_COUNTERPARTIES,
    METHOD_GET_COUNTERPARTY_ADDRESSES,
    METHOD_GET_COUNTERPARTY_CONTACT_PERSONS,
    DOCUMENT_LIST_PAGE_SIZE,
    METHOD_GET_DOCUMENT,
    METHOD_GET_DOCUMENT_LIST,
    METHOD_INIT_PAYOUT,
    METHOD_GET_STATUS,
    METHOD_GET_STATUS_DOCUMENTS,
    METHOD_GET_WAREHOUSES,
    METHOD_DELETE,
    METHOD_SAVE,
    METHOD_UPDATE,
    METHOD_WALLET_MANAGEMENT,
    METHOD_SEARCH_SETTLEMENTS,
    MODEL_ADDRESS,
    MODEL_COMMON,
    MODEL_CONTACT_PERSON,
    MODEL_COUNTERPARTY,
    MODEL_INTERNET_DOCUMENT,
    MODEL_PAYMENT,
    MODEL_TRACKING_DOCUMENT,
    NP_API_SYSTEM,
    SEARCH_LIMIT,
    SEARCH_PAGE,
)
from app.nova_poshta.exceptions import (
    NovaPoshtaApiError,
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

    @staticmethod
    def _build_log_payload(
        model_name: str,
        called_method: str,
        method_properties: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build a request payload for logging without the API key."""
        return {
            "modelName": model_name,
            "calledMethod": called_method,
            "methodProperties": method_properties or {},
        }

    async def _post_json(
        self,
        payload: dict[str, Any],
        *,
        model_name: str,
        called_method: str,
        method_properties: dict[str, Any] | None,
        headers: dict[str, str] | None = None,
        auth_mode: str = "apiKey",
    ) -> dict[str, Any]:
        session = await self._ensure_session()
        log_payload = self._build_log_payload(
            model_name,
            called_method,
            method_properties,
        )
        if "system" in payload:
            log_payload["system"] = payload["system"]
        log_payload["auth"] = auth_mode

        logger.info(
            "Nova Poshta API request JSON: {}",
            json.dumps(log_payload, ensure_ascii=False),
        )

        try:
            async with session.post(API_URL, json=payload, headers=headers) as response:
                raw_body = await response.text()

                try:
                    data = json.loads(raw_body)
                except json.JSONDecodeError as exc:
                    msg = "Nova Poshta API returned a non-JSON response"
                    logger.error("{}: {}", msg, raw_body[:500])
                    raise NovaPoshtaResponseError(msg) from exc

                logger.info(
                    "Nova Poshta API response JSON: {}",
                    json.dumps(data, ensure_ascii=False),
                )

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
                        "Nova Poshta request succeeded: model={} method={} auth={}",
                        model_name,
                        called_method,
                        auth_mode,
                    )
                else:
                    logger.error(
                        "Nova Poshta request failed: model={} method={} auth={} "
                        "errors={} response={}",
                        model_name,
                        called_method,
                        auth_mode,
                        data.get("errors"),
                        json.dumps(data, ensure_ascii=False),
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

    async def _call(
        self,
        model_name: str,
        called_method: str,
        method_properties: dict[str, Any] | None = None,
        *,
        system: str | None = None,
    ) -> dict[str, Any]:
        """Call the public JSON API authenticated with apiKey (unchanged behavior)."""
        payload: dict[str, Any] = {
            "apiKey": self._api_key,
            "modelName": model_name,
            "calledMethod": called_method,
            "methodProperties": method_properties or {},
        }
        if system:
            payload["system"] = system
        return await self._post_json(
            payload,
            model_name=model_name,
            called_method=called_method,
            method_properties=method_properties,
            auth_mode="apiKey",
        )

    async def _call_with_oauth(
        self,
        model_name: str,
        called_method: str,
        method_properties: dict[str, Any] | None = None,
        *,
        oauth_access_token: str,
        system: str | None = None,
    ) -> dict[str, Any]:
        """Call the JSON API with TokenOAuth2 (no apiKey in body)."""
        token = oauth_access_token.strip()
        if not token:
            msg = "OAuth access_token is required for this Nova Poshta call"
            raise ValueError(msg)
        payload: dict[str, Any] = {
            "modelName": model_name,
            "calledMethod": called_method,
            "methodProperties": method_properties or {},
        }
        if system:
            payload["system"] = system
        return await self._post_json(
            payload,
            model_name=model_name,
            called_method=called_method,
            method_properties=method_properties,
            headers={"TokenOAuth2": token},
            auth_mode="TokenOAuth2",
        )

    async def get_status(self) -> dict[str, Any]:
        """Call Common/getServiceTypes and return parsed JSON."""
        return await self._call(MODEL_COMMON, METHOD_GET_STATUS)

    async def get_status_documents(
        self,
        documents: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Track TTN statuses through TrackingDocument.getStatusDocuments."""
        return await self._call(
            MODEL_TRACKING_DOCUMENT,
            METHOD_GET_STATUS_DOCUMENTS,
            {"Documents": documents},
        )

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

    async def search_settlements(self, city_name: str) -> dict[str, Any]:
        """Search cities and settlements by name."""
        return await self._call(
            MODEL_ADDRESS,
            METHOD_SEARCH_SETTLEMENTS,
            {
                "CityName": city_name,
                "Limit": SEARCH_LIMIT,
                "Page": SEARCH_PAGE,
            },
        )

    async def get_warehouses(
        self,
        city_ref: str,
        *,
        find_by_string: str = "",
    ) -> dict[str, Any]:
        """Load warehouses for the selected city."""
        return await self._call(
            MODEL_ADDRESS,
            METHOD_GET_WAREHOUSES,
            {
                "CityRef": city_ref,
                "FindByString": find_by_string,
                "Limit": SEARCH_LIMIT,
                "Page": SEARCH_PAGE,
            },
        )

    async def get_sender_counterparties(self) -> dict[str, Any]:
        """Load sender counterparties linked to the API key."""
        return await self._call(
            MODEL_COUNTERPARTY,
            METHOD_GET_COUNTERPARTIES,
            {
                "CounterpartyProperty": "Sender",
                "Page": SEARCH_PAGE,
            },
        )

    async def get_recipient_counterparties(
        self,
        *,
        find_by_string: str = "",
    ) -> dict[str, Any]:
        """Load recipient counterparties linked to the API key."""
        properties: dict[str, Any] = {
            "CounterpartyProperty": "Recipient",
            "Page": SEARCH_PAGE,
        }
        if find_by_string:
            properties["FindByString"] = find_by_string

        return await self._call(MODEL_COUNTERPARTY, METHOD_GET_COUNTERPARTIES, properties)

    async def get_counterparty_contact_persons(
        self,
        counterparty_ref: str,
    ) -> dict[str, Any]:
        """Load contact persons for a counterparty."""
        return await self._call(
            MODEL_COUNTERPARTY,
            METHOD_GET_COUNTERPARTY_CONTACT_PERSONS,
            {
                "Ref": counterparty_ref,
                "Page": SEARCH_PAGE,
            },
        )

    async def get_catalog_counterparty(
        self,
        phone: str,
        last_name: str,
    ) -> dict[str, Any]:
        """Find a counterparty by phone number and last name."""
        properties: dict[str, Any] = {"Phone": phone}
        if last_name:
            properties["LastName"] = last_name

        return await self._call(
            MODEL_COUNTERPARTY,
            METHOD_GET_CATALOG_COUNTERPARTY,
            properties,
        )

    async def get_counterparty_addresses(
        self,
        counterparty_ref: str,
    ) -> dict[str, Any]:
        """Load addresses linked to a counterparty."""
        return await self._call(
            MODEL_COUNTERPARTY,
            METHOD_GET_COUNTERPARTY_ADDRESSES,
            {
                "Ref": counterparty_ref,
                "Page": SEARCH_PAGE,
            },
        )

    async def save_recipient_counterparty(
        self,
        *,
        first_name: str,
        last_name: str,
        middle_name: str,
        phone: str,
        city_ref: str,
    ) -> dict[str, Any]:
        """Create a private-person recipient counterparty."""
        properties: dict[str, Any] = {
            "FirstName": first_name,
            "LastName": last_name,
            "Phone": phone,
            "CounterpartyType": "PrivatePerson",
            "CounterpartyProperty": "Recipient",
            "CityRef": city_ref,
        }
        if middle_name:
            properties["MiddleName"] = middle_name

        return await self._call(MODEL_COUNTERPARTY, METHOD_SAVE, properties)

    async def update_recipient_counterparty(
        self,
        *,
        counterparty_ref: str,
        first_name: str,
        last_name: str,
        middle_name: str,
        phone: str,
        city_ref: str,
    ) -> dict[str, Any]:
        """Update an existing private-person recipient counterparty."""
        properties: dict[str, Any] = {
            "Ref": counterparty_ref,
            "FirstName": first_name,
            "LastName": last_name,
            "Phone": phone,
            "CounterpartyType": "PrivatePerson",
            "CounterpartyProperty": "Recipient",
            "CityRef": city_ref,
        }
        if middle_name:
            properties["MiddleName"] = middle_name

        return await self._call(MODEL_COUNTERPARTY, METHOD_UPDATE, properties)

    async def save_contact_person(
        self,
        *,
        counterparty_ref: str,
        first_name: str,
        last_name: str,
        middle_name: str,
        phone: str,
    ) -> dict[str, Any]:
        """Create a contact person for a counterparty."""
        properties: dict[str, Any] = {
            "CounterpartyRef": counterparty_ref,
            "FirstName": first_name,
            "LastName": last_name,
            "Phone": phone,
        }
        if middle_name:
            properties["MiddleName"] = middle_name

        return await self._call(MODEL_CONTACT_PERSON, METHOD_SAVE, properties)

    async def update_contact_person(
        self,
        *,
        contact_ref: str,
        counterparty_ref: str,
        first_name: str,
        last_name: str,
        middle_name: str,
        phone: str,
    ) -> dict[str, Any]:
        """Update a contact person for a counterparty."""
        properties: dict[str, Any] = {
            "Ref": contact_ref,
            "CounterpartyRef": counterparty_ref,
            "FirstName": first_name,
            "LastName": last_name,
            "Phone": phone,
        }
        if middle_name:
            properties["MiddleName"] = middle_name

        return await self._call(MODEL_CONTACT_PERSON, METHOD_UPDATE, properties)

    async def get_document_list(
        self,
        *,
        date_time_from: str,
        date_time_to: str,
        page: str = "1",
        limit: str = DOCUMENT_LIST_PAGE_SIZE,
    ) -> dict[str, Any]:
        """Fetch a page of InternetDocuments for the configured API key."""
        return await self._call(
            MODEL_INTERNET_DOCUMENT,
            METHOD_GET_DOCUMENT_LIST,
            {
                "DateTimeFrom": date_time_from,
                "DateTimeTo": date_time_to,
                "Page": page,
                "Limit": limit,
            },
        )

    async def get_document(self, document_ref: str) -> dict[str, Any]:
        """Fetch a single InternetDocument by Ref."""
        return await self._call(
            MODEL_INTERNET_DOCUMENT,
            METHOD_GET_DOCUMENT,
            {"Ref": document_ref},
        )

    async def init_payout(
        self,
        *,
        phone: str,
        oauth_access_token: str,
        document_number: str | None = None,
    ) -> dict[str, Any]:
        """Start Cash2Card payout registration (Payment.initPayout via TokenOAuth2)."""
        method_properties: dict[str, Any] = {"Phone": phone.strip()}
        if document_number:
            method_properties["Number"] = document_number.strip()

        response = await self._call_with_oauth(
            MODEL_PAYMENT,
            METHOD_INIT_PAYOUT,
            method_properties,
            oauth_access_token=oauth_access_token,
            system=NP_API_SYSTEM,
        )
        if response.get("success") is not True:
            errors = [str(error) for error in response.get("errors") or []]
            msg = "; ".join(errors) or "Nova Poshta failed to init Cash2Card payout"
            raise NovaPoshtaApiError(msg, errors=errors)

        data = response.get("data") or []
        if not data or not isinstance(data[0], dict):
            msg = "Payment.initPayout returned an empty payload"
            raise NovaPoshtaApiError(msg)

        return data[0]

    async def save_internet_document(
        self,
        method_properties: dict[str, Any],
        *,
        use_cash2card: bool = False,
    ) -> dict[str, Any]:
        """Create an express waybill through InternetDocument.save."""
        response = await self._call(
            MODEL_INTERNET_DOCUMENT,
            METHOD_SAVE,
            method_properties,
            system=NP_API_SYSTEM if use_cash2card else None,
        )
        if response.get("success") is not True:
            errors = [str(error) for error in response.get("errors") or []]
            msg = "; ".join(errors) or "Nova Poshta failed to create TTN"
            raise NovaPoshtaApiError(msg, errors=errors)
        return response

    async def delete_internet_document(self, document_ref: str) -> dict[str, Any]:
        """Delete an express waybill through InternetDocument.delete."""
        response = await self._call(
            MODEL_INTERNET_DOCUMENT,
            METHOD_DELETE,
            {"DocumentRefs": [document_ref.strip()]},
        )
        if response.get("success") is not True:
            errors = [str(error) for error in response.get("errors") or []]
            msg = "; ".join(errors) or "Nova Poshta failed to delete TTN"
            raise NovaPoshtaApiError(msg, errors=errors)
        return response
