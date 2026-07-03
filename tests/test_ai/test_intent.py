from decimal import Decimal

from app.services.ai.intent import IntentDetectionService
from app.services.ai.schemas import Intent
from tests.test_ai.fakes import FakeLLMClient


class TestIntentDetection:
    async def test_detects_create_transaction(self):
        client = FakeLLMClient([
            {"intent": "create_transaction", "confidence": 0.95, "reasoning": "sotuv haqida"}
        ])
        service = IntentDetectionService(client)

        result = await service.detect("1 million so'mga tovar sotdim")

        assert result.intent == Intent.CREATE_TRANSACTION
        assert result.confidence == Decimal("0.95")

    async def test_unknown_intent_string_falls_back_to_unknown(self):
        client = FakeLLMClient([{"intent": "do_something_weird", "confidence": 0.9}])
        service = IntentDetectionService(client)

        result = await service.detect("blah blah")

        assert result.intent == Intent.UNKNOWN

    async def test_empty_message_returns_unknown_without_calling_llm(self):
        client = FakeLLMClient([])
        service = IntentDetectionService(client)

        result = await service.detect("   ")

        assert result.intent == Intent.UNKNOWN
        assert result.confidence == Decimal("1.0")
        assert client.calls == []

    async def test_confidence_is_clamped_between_0_and_1(self):
        client = FakeLLMClient([{"intent": "smalltalk", "confidence": 5}])
        service = IntentDetectionService(client)

        result = await service.detect("salom")

        assert result.confidence == Decimal("1")

    async def test_malformed_llm_response_does_not_crash(self):
        client = FakeLLMClient(["bu JSON emas, oddiy matn"])
        service = IntentDetectionService(client)

        result = await service.detect("nimadir")

        assert result.intent == Intent.UNKNOWN
        assert result.confidence == Decimal("0.0")
