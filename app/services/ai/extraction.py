"""Entity Extraction — matndan tranzaksiya/qarz to'lovi maydonlarini ajratish."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from loguru import logger

from app.services.ai.client import AIClientError, LLMClient, get_ai_client
from app.services.ai.prompts import DEBT_PAYMENT_EXTRACTION_PROMPT, ENTITY_EXTRACTION_PROMPT
from app.services.ai.schemas import ExtractedDebtPayment, ExtractedTransaction

REQUIRED_TRANSACTION_FIELDS = ("transaction_type", "amount")
REQUIRED_DEBT_PAYMENT_FIELDS = ("counterparty_name", "amount")


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _to_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _to_confidence(value) -> Decimal:
    d = _to_decimal(value) or Decimal("0")
    return max(Decimal("0"), min(Decimal("1"), d))


class EntityExtractionService:
    """Tranzaksiya yoki qarz to'lovi xabaridan struktura ajratadi."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._client = llm_client or get_ai_client()

    async def extract_transaction(self, message: str) -> ExtractedTransaction:
        try:
            raw = await self._client.complete_json(
                system=ENTITY_EXTRACTION_PROMPT,
                user=message,
            )
        except AIClientError as e:
            logger.error(f"Entity extraction xato: {e}")
            return ExtractedTransaction(
                confidence=Decimal("0"),
                missing_fields=list(REQUIRED_TRANSACTION_FIELDS),
            )

        amount = _to_decimal(raw.get("amount"))
        transaction_type = raw.get("transaction_type")

        missing = list(raw.get("missing_fields") or [])
        for field_name, field_value in (("transaction_type", transaction_type), ("amount", amount)):
            if field_value in (None, "") and field_name not in missing:
                missing.append(field_name)

        return ExtractedTransaction(
            transaction_type=transaction_type,
            amount=amount,
            currency=str(raw.get("currency") or "UZS"),
            description=raw.get("description"),
            category_hint=raw.get("category_hint"),
            counterparty_name=raw.get("counterparty_name"),
            payment_method=raw.get("payment_method"),
            is_credit=bool(raw.get("is_credit", False)),
            transaction_date=_to_date(raw.get("transaction_date")),
            confidence=_to_confidence(raw.get("confidence")),
            missing_fields=missing,
        )

    async def extract_debt_payment(self, message: str) -> ExtractedDebtPayment:
        try:
            raw = await self._client.complete_json(
                system=DEBT_PAYMENT_EXTRACTION_PROMPT,
                user=message,
            )
        except AIClientError as e:
            logger.error(f"Debt payment extraction xato: {e}")
            return ExtractedDebtPayment(
                confidence=Decimal("0"),
                missing_fields=list(REQUIRED_DEBT_PAYMENT_FIELDS),
            )

        counterparty = raw.get("counterparty_name")
        amount = _to_decimal(raw.get("amount"))

        missing = list(raw.get("missing_fields") or [])
        for field_name, field_value in (("counterparty_name", counterparty), ("amount", amount)):
            if field_value in (None, "") and field_name not in missing:
                missing.append(field_name)

        return ExtractedDebtPayment(
            counterparty_name=counterparty,
            amount=amount,
            payment_date=_to_date(raw.get("payment_date")),
            confidence=_to_confidence(raw.get("confidence")),
            missing_fields=missing,
        )
