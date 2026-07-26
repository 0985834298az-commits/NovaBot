from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger

from app.constants import (
    SENDER_CITY_AREA,
    SENDER_CITY_QUERY,
    SENDER_WAREHOUSE_NUMBER,
)
from app.nova_poshta.client import NovaPoshtaClient
from app.nova_poshta.exceptions import NovaPoshtaApiError, NovaPoshtaError
from app.services.ttn_service import (
    find_warehouse_by_number,
    parse_settlements,
    parse_warehouses,
)


@dataclass(frozen=True, slots=True)
class CachedSenderLocation:
    """Resolved sender city and warehouse refs."""

    sender_city: dict[str, str]
    sender_warehouse: dict[str, str]


_location: CachedSenderLocation | None = None
_error: str | None = None


def find_sender_settlement(
    settlements: list[dict[str, str]],
) -> dict[str, str] | None:
    """Find the default sender settlement in Mykolaiv region."""
    area_match = SENDER_CITY_AREA.casefold()
    city_match = SENDER_CITY_QUERY.casefold()

    for settlement in settlements:
        name = settlement["name"].casefold()
        area = settlement["area"].casefold()
        if city_match in name and area_match in area:
            return settlement

    for settlement in settlements:
        if city_match in settlement["name"].casefold():
            return settlement

    return None


def is_sender_cache_ready() -> bool:
    """Return True when sender refs were resolved at startup."""
    return _location is not None


def get_sender_cache_error() -> str | None:
    """Return the sender cache initialization error, if any."""
    return _error


def get_cached_sender_location() -> dict[str, dict[str, str]]:
    """Return cached sender city and warehouse data."""
    if _location is None:
        msg = _error or "Sender location is not configured"
        raise NovaPoshtaApiError(msg)

    return {
        "sender_city": _location.sender_city,
        "sender_warehouse": _location.sender_warehouse,
    }


async def initialize_sender_cache(api_key: str) -> None:
    """Resolve and cache default sender city and warehouse refs."""
    global _location, _error

    if not api_key.strip():
        _location = None
        _error = "Nova Poshta API key is not available for sender cache initialization"
        logger.error(_error)
        return

    try:
        async with NovaPoshtaClient(api_key) as client:
            city_response = await client.search_settlements(SENDER_CITY_QUERY)
            settlements = parse_settlements(city_response)
            sender_city = find_sender_settlement(settlements)
            if sender_city is None:
                msg = (
                    "Sender city was not found: "
                    f"{SENDER_CITY_QUERY}, {SENDER_CITY_AREA}"
                )
                raise NovaPoshtaApiError(msg)

            warehouse_response = await client.get_warehouses(
                sender_city["delivery_city"],
                find_by_string=SENDER_WAREHOUSE_NUMBER,
            )
            warehouses = parse_warehouses(warehouse_response)
            sender_warehouse = find_warehouse_by_number(
                warehouses,
                SENDER_WAREHOUSE_NUMBER,
            )
            if sender_warehouse is None:
                msg = f"Sender warehouse №{SENDER_WAREHOUSE_NUMBER} was not found"
                raise NovaPoshtaApiError(msg)

        _location = CachedSenderLocation(
            sender_city={"delivery_city": sender_city["delivery_city"]},
            sender_warehouse=sender_warehouse,
        )
        _error = None
        logger.info(
            "Sender cache initialized: city_ref={} warehouse_ref={} warehouse_number={}",
            sender_city["delivery_city"],
            sender_warehouse["ref"],
            sender_warehouse["number"],
        )
    except NovaPoshtaError as exc:
        _location = None
        _error = str(exc)
        logger.error("Failed to initialize sender cache: {}", exc)
    except Exception as exc:
        _location = None
        _error = str(exc)
        logger.exception("Unexpected error while initializing sender cache")


async def resolve_startup_api_key(
    *,
    configured_api_key: str | None,
    session_factory: Any,
) -> str | None:
    """Pick an API key for sender cache initialization."""
    if configured_api_key:
        return configured_api_key

    from app.repositories.user_repository import UserRepository

    async with session_factory() as session:
        repository = UserRepository(session)
        return await repository.get_any_api_key()
