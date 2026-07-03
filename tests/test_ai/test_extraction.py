from decimal import Decimal

from app.services.ai.extraction import EntityExtractionService
from tests.test_ai.fakes import FakeLLMClient


class TestTransactionExtraction:
    async def test_extracts_full_transaction(self):
        client = FakeLLMClient([{
            "transaction_type": "income",
            "amount": 1000000,
            "currency": "UZS",
            "description": "Tovar sotuvi",
            "category_hint": "Sotuv",
            "counterparty_name": "Aziz",
            "payment_method": "cash",
            "is_credit": False,
            "transaction_date": None,
            "confidence": 0.9,
            "missing_fields": [],
        }])
        service = EntityExtractionService(client)

        result = await service.extract_transaction("Azizga 1 million so'mga tovar sotdim")

        assert result.transaction_type == "income"
        assert result.amount == Decimal("1000000")
        assert result.counterparty_name == "Aziz"
        assert result.missing_fields == []

    async def test_missing_amount_is_flagged(self):
        client = FakeLLMClient([{
            "transaction_type": "expense",
            "amount": None,
            "confidence": 0.6,
            "missing_fields": [],
        }])
        service = EntityExtractionService(client)

        result = await service.extract_transaction("xarajat qildim")

        assert "amount" in result.missing_fields

    async def test_missing_transaction_type_is_flagged(self):
        client = FakeLLMClient([{"amount": 50000, "confidence": 0.6, "missing_fields": []}])
        service = EntityExtractionService(client)

        result = await service.extract_transaction("50 ming so'm")

        assert "transaction_type" in result.missing_fields

    async def test_llm_error_returns_missing_required_fields(self):
        client = FakeLLMClient(["not json at all {{{"])
        service = EntityExtractionService(client)

        result = await service.extract_transaction("nimadir")

        assert "amount" in result.missing_fields
        assert "transaction_type" in result.missing_fields
        assert result.confidence == Decimal("0")


class TestDebtPaymentExtraction:
    async def test_extracts_debt_payment(self):
        client = FakeLLMClient([{
            "counterparty_name": "Aziz",
            "amount": 500000,
            "payment_date": None,
            "confidence": 0.8,
            "missing_fields": [],
        }])
        service = EntityExtractionService(client)

        result = await service.extract_debt_payment("Aziz 500 ming to'ladi")

        assert result.counterparty_name == "Aziz"
        assert result.amount == Decimal("500000")

    async def test_missing_counterparty_is_flagged(self):
        client = FakeLLMClient([{"amount": 100000, "confidence": 0.5, "missing_fields": []}])
        service = EntityExtractionService(client)

        result = await service.extract_debt_payment("100 ming to'ladi")

        assert "counterparty_name" in result.missing_fields
