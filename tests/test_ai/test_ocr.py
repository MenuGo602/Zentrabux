import pytest
from decimal import Decimal

from app.services.ai.ocr import OCRService
from tests.test_ai.fakes import FakeLLMClient


class TestOCRService:
    async def test_extracts_receipt_data(self):
        client = FakeLLMClient([{
            "raw_text": "Magazin XYZ\nJami: 150000",
            "merchant_name": "Magazin XYZ",
            "total_amount": 150000,
            "currency": "UZS",
            "purchase_date": "2026-06-15",
            "line_items": ["Non", "Sut"],
            "confidence": 0.85,
        }])
        service = OCRService(client)

        result = await service.extract_from_image("ZmFrZS1iYXNlNjQ=", "image/jpeg")

        assert result.merchant_name == "Magazin XYZ"
        assert result.total_amount == Decimal("150000")
        assert result.line_items == ["Non", "Sut"]
        # Rasm haqiqatan ham LLM chaqiruviga uzatilganini tekshiramiz
        assert client.calls[0]["image_base64"] == "ZmFrZS1iYXNlNjQ="

    async def test_rejects_unsupported_media_type(self):
        service = OCRService(FakeLLMClient([]))

        with pytest.raises(ValueError):
            await service.extract_from_image("data", "application/pdf")

    async def test_llm_failure_returns_zero_confidence_result(self):
        client = FakeLLMClient(["not valid json"])
        service = OCRService(client)

        result = await service.extract_from_image("ZmFrZQ==", "image/png")

        assert result.confidence == Decimal("0")
