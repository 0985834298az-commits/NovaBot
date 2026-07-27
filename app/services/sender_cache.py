from __future__ import annotations

from dataclasses import dataclass

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

    api_key: str
    sender_city: dict[str, str]
    sender_warehouse: dict[str, str]


_user_locations: dict[int, CachedSenderLocation] = {}
_user_errors: dict[int, str] = {}


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


def invalidate_sender_cache(telegram_user_id: int) -> None:
    """Drop cached sender refs for a Telegram user."""
    _user_locations.pop(telegram_user_id, None)
    _user_errors.pop(telegram_user_id, None)


def is_sender_cache_ready(telegram_user_id: int) -> bool:
    """Return True when sender refs were resolved for the user."""
    return telegram_user_id in _user_locations


def get_sender_cache_error(telegram_user_id: int) -> str | None:
    """Return sender cache initialization error for the user, if any."""
    return _user_errors.get(telegram_user_id)


def get_cached_sender_location(telegram_user_id: int) -> dict[str, dict[str, str]]:
    """Return cached sender city and warehouse data for the user."""
    location = _user_locations.get(telegram_user_id)
    if location is None:
        msg = _user_errors.get(telegram_user_id) or "Sender location is not configured"
        raise NovaPoshtaApiError(msg)

    return {
        "sender_city": location.sender_city,
        "sender_warehouse": location.sender_warehouse,
    }


async def ensure_sender_cache(telegram_user_id: int, api_key: str) -> bool:
    """Resolve sender refs for the user's active Nova Poshta account."""
    normalized_key = api_key.strip()
    if not normalized_key:
        invalidate_sender_cache(telegram_user_id)
        _user_errors[telegram_user_id] = (
            "Nova Poshta API key is not available for sender cache initialization"
        )
        logger.error(
            "Sender cache for user {} was not initialized: empty API key",
            telegram_user_id,
        )
        return False

    cached = _user_locations.get(telegram_user_id)
    if cached is not None and cached.api_key == normalized_key:
        return True

    await _initialize_sender_cache(telegram_user_id, normalized_key)
    return telegram_user_id in _user_locations


async def _initialize_sender_cache(telegram_user_id: int, api_key: str) -> None:
    """Resolve and cache default sender city and warehouse refs."""
    invalidate_sender_cache(telegram_user_id)

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

        _user_locations[telegram_user_id] = CachedSenderLocation(
            api_key=api_key,
            sender_city={"delivery_city": sender_city["delivery_city"]},
            sender_warehouse=sender_warehouse,
        )
        logger.info(
            "Sender cache initialized for user {}: city_ref={} warehouse_ref={} warehouse_number={}",
            telegram_user_id,
            sender_city["delivery_city"],
            sender_warehouse["ref"],
            sender_warehouse["number"],
        )
    except NovaPoshtaError as exc:
        _user_errors[telegram_user_id] = str(exc)
        logger.error(
            "Failed to initialize sender cache for user {}: {}",
            telegram_user_id,
            exc,
        )
    except Exception as exc:
        _user_errors[telegram_user_id] = str(exc)
        logger.exception(
            "Unexpected error while initializing sender cache for user {}",
            telegram_user_id,
        )
