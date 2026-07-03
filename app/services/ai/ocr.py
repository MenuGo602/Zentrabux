"""OCR Service — chek/faktura rasmlaridan ma'lumot o'qish.

Vision-qobiliyatli LLM (GPT-4o-mini yoki Claude) orqali ishlaydi — alohida
OCR kutubxonasi (tesseract va h.k.) talab qilinmaydi, chunki zamonaviy
multimodal modellar chek o'qishda yaxshi natija beradi va bitta provayder
qatlamidan (``LLMClient``) foydalanish arxitekturani soddalashtiradi.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from loguru import logger

from app.services.ai.client import AIClientError, LLMClient, get_ai_client
from app.services.ai.prompts import OCR_EXTRACTION_PROMPT
from app.services.ai.schemas import OCRResult

SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp"}


class OCRService:
    """Chek rasmidan ``OCRResult`` qaytaradi."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._client = llm_client or get_ai_client()

    async def extract_from_image(
        self,
        image_base64: str,
        media_type: str = "image/jpeg",
    ) -> OCRResult:
        if media_type not in SUPPORTED_MEDIA_TYPES:
            raise ValueError(
                f"Qo'llab-quvvatlanmaydigan rasm formati: {media_type}. "
                f"Ruxsat etilgan: {', '.join(sorted(SUPPORTED_MEDIA_TYPES))}"
            )

        try:
            raw = await self._client.complete_json(
                system=OCR_EXTRACTION_PROMPT,
                user="Bu chek/faktura rasmini o'qib, ma'lumotlarini ajratib ber.",
                image_base64=image_base64,
                image_media_type=media_type,
            )
        except AIClientError as e:
            logger.error(f"OCR xato: {e}")
            return OCRResult(confidence=Decimal("0"))

        try:
            total_amount = Decimal(str(raw["total_amount"])) if raw.get("total_amount") is not None else None
        except (InvalidOperation, TypeError, ValueError):
            total_amount = None

        purchase_date = None
        if raw.get("purchase_date"):
            try:
                purchase_date = date.fromisoformat(str(raw["purchase_date"]))
            except ValueError:
                purchase_date = None

        try:
            confidence = max(Decimal("0"), min(Decimal("1"), Decimal(str(raw.get("confidence", 0)))))
        except (InvalidOperation, TypeError):
            confidence = Decimal("0")

        return OCRResult(
            raw_text=str(raw.get("raw_text", "")),
            merchant_name=raw.get("merchant_name"),
            total_amount=total_amount,
            currency=str(raw.get("currency") or "UZS"),
            purchase_date=purchase_date,
            line_items=list(raw.get("line_items") or []),
            confidence=confidence,
        )
