from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from loguru import logger

from app.models.nova_poshta_account import NovaPoshtaAccount
from app.repositories.nova_poshta_account_repository import NovaPoshtaAccountRepository
from app.repositories.user_repository import UserRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.sender_cache import ensure_sender_cache, invalidate_sender_cache
from app.utils.money import format_money_uah, parse_cod_amount


class SelectionAction(str, Enum):
    """Result of smart account selection before TTN creation."""

    USE_CURRENT = "use_current"
    AUTO_SWITCHED = "auto_switched"
    NO_FIT = "no_fit"
    WARN_EXCEED = "warn_exceed"


@dataclass(frozen=True, slots=True)
class AccountUsageInfo:
    """Monthly COD usage for one Nova Poshta account."""

    account: NovaPoshtaAccount
    current_month_cod: Decimal
    monthly_limit: Decimal

    @property
    def remaining(self) -> Decimal:
        return max(Decimal(0), self.monthly_limit - self.current_month_cod)


@dataclass(frozen=True, slots=True)
class AccountSelectionOutcome:
    """Selected account and metadata for TTN creation."""

    action: SelectionAction
    selected_account: NovaPoshtaAccount
    cod_amount: Decimal
    usages: tuple[AccountUsageInfo, ...]
    previous_account: NovaPoshtaAccount | None = None

    @property
    def requires_user_choice(self) -> bool:
        return self.action in {SelectionAction.NO_FIT, SelectionAction.WARN_EXCEED}


async def build_account_usages(
    account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
    telegram_user_id: int,
) -> list[AccountUsageInfo]:
    """Build monthly usage stats for every saved account."""
    accounts = await account_repository.get_all_accounts(telegram_user_id)
    usages: list[AccountUsageInfo] = []
    for account in accounts:
        current_month_cod = await waybill_repository.get_current_month_cod_total(account.id)
        usages.append(
            AccountUsageInfo(
                account=account,
                current_month_cod=current_month_cod,
                monthly_limit=Decimal(account.monthly_limit),
            ),
        )
    return usages


def format_account_usage_block(usage: AccountUsageInfo) -> str:
    """Format one account usage section for Telegram."""
    indicator = "🟢" if usage.account.is_active else "⚪️"
    return (
        f"{indicator} {usage.account.account_name}\n"
        f"{format_money_uah(usage.current_month_cod)} / "
        f"{format_money_uah(usage.monthly_limit)}"
    )


def format_available_accounts(usages: list[AccountUsageInfo]) -> str:
    """Format all account balances for limit messages."""
    return "\n\n".join(format_account_usage_block(usage) for usage in usages)


async def resolve_account_for_cod(
    *,
    account_repository: NovaPoshtaAccountRepository,
    waybill_repository: WaybillRepository,
    user_repository: UserRepository,
    telegram_user_id: int,
    cod_amount: Decimal,
    force_current: bool = False,
) -> AccountSelectionOutcome | None:
    """Pick the best Nova Poshta account for a COD amount."""
    active_account = await account_repository.get_active_account(telegram_user_id)
    if active_account is None:
        return None

    usages = await build_account_usages(
        account_repository,
        waybill_repository,
        telegram_user_id,
    )
    usage_by_id = {usage.account.id: usage for usage in usages}
    active_usage = usage_by_id.get(active_account.id)
    if active_usage is None:
        return None

    logger.info(
        "Account selection check: user={} current_account={} remaining={} cod={} force_current={}",
        telegram_user_id,
        active_account.account_name,
        format_money_uah(active_usage.remaining),
        format_money_uah(cod_amount),
        force_current,
    )

    if force_current or active_usage.remaining >= cod_amount:
        logger.info(
            "Account selection result: user={} selected={} reason=use_current remaining={}",
            telegram_user_id,
            active_account.account_name,
            format_money_uah(active_usage.remaining),
        )
        return AccountSelectionOutcome(
            action=SelectionAction.USE_CURRENT,
            selected_account=active_account,
            cod_amount=cod_amount,
            usages=tuple(usages),
        )

    auto_switching = await user_repository.get_auto_account_switching(telegram_user_id)
    if auto_switching:
        candidates = [usage for usage in usages if usage.remaining >= cod_amount]
        if candidates:
            best_usage = max(candidates, key=lambda usage: usage.remaining)
            selected_account = best_usage.account
            if selected_account.id != active_account.id:
                await account_repository.set_active_account(
                    selected_account.id,
                    telegram_user_id,
                )
                invalidate_sender_cache(telegram_user_id)
                await ensure_sender_cache(telegram_user_id, selected_account.api_key)
                logger.info(
                    "Account selection result: user={} previous={} selected={} "
                    "reason=auto_switch previous_remaining={} selected_remaining={}",
                    telegram_user_id,
                    active_account.account_name,
                    selected_account.account_name,
                    format_money_uah(active_usage.remaining),
                    format_money_uah(best_usage.remaining),
                )
                return AccountSelectionOutcome(
                    action=SelectionAction.AUTO_SWITCHED,
                    selected_account=selected_account,
                    previous_account=active_account,
                    cod_amount=cod_amount,
                    usages=tuple(usages),
                )

            logger.info(
                "Account selection result: user={} selected={} reason=use_current",
                telegram_user_id,
                selected_account.account_name,
            )
            return AccountSelectionOutcome(
                action=SelectionAction.USE_CURRENT,
                selected_account=selected_account,
                cod_amount=cod_amount,
                usages=tuple(usages),
            )

        logger.info(
            "Account selection result: user={} current={} reason=no_fit remaining={}",
            telegram_user_id,
            active_account.account_name,
            format_money_uah(active_usage.remaining),
        )
        return AccountSelectionOutcome(
            action=SelectionAction.NO_FIT,
            selected_account=active_account,
            cod_amount=cod_amount,
            usages=tuple(usages),
            previous_account=active_account,
        )

    logger.info(
        "Account selection result: user={} current={} reason=warn_exceed remaining={}",
        telegram_user_id,
        active_account.account_name,
        format_money_uah(active_usage.remaining),
    )
    return AccountSelectionOutcome(
        action=SelectionAction.WARN_EXCEED,
        selected_account=active_account,
        cod_amount=cod_amount,
        usages=tuple(usages),
        previous_account=active_account,
    )


async def activate_account_for_user(
    *,
    account_repository: NovaPoshtaAccountRepository,
    telegram_user_id: int,
    account_id: int,
) -> NovaPoshtaAccount | None:
    """Activate an account and refresh sender cache."""
    account = await account_repository.set_active_account(account_id, telegram_user_id)
    if account is None:
        return None

    invalidate_sender_cache(telegram_user_id)
    await ensure_sender_cache(telegram_user_id, account.api_key)
    return account


def cod_amount_from_string(value: str) -> Decimal:
    """Parse COD text safely, defaulting invalid values to zero."""
    try:
        return parse_cod_amount(value)
    except ValueError:
        return Decimal(0)
