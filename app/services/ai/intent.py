"""Intent Detection — foydalanuvchi xabaridan niyatni aniqlash."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from loguru import logger

from app.services.ai.client import AIClientError, LLMClient, get_ai_client
from app.services.ai.prompts import INTENT_DETECTION_PROMPT
from app.services.ai.schemas import Intent, IntentResult


class IntentDetectionService:
    """Foydalanuvchi xabarini ``Intent`` enumiga moslaydi."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._client = llm_client or get_ai_client()

    async def detect(self, message: str) -> IntentResult:
        if not message or not message.strip():
            return IntentResult(intent=Intent.UNKNOWN, confidence=Decimal("1.0"), reasoning="Bo'sh xabar")

        try:
            raw = await self._client.complete_json(
                system=INTENT_DETECTION_PROMPT,
                user=message,
            )
        except AIClientError as e:
            logger.error(f"Intent detection xato: {e}")
            return IntentResult(
                intent=Intent.UNKNOWN,
                confidence=Decimal("0.0"),
                reasoning=f"AI xatosi: {e}",
            )

        intent_raw = str(raw.get("intent", "unknown")).strip().lower()
        try:
            intent = Intent(intent_raw)
        except ValueError:
            logger.warning(f"Noma'lum intent qaytdi: {intent_raw!r} — UNKNOWN'ga o'tkazildi")
            intent = Intent.UNKNOWN

        try:
            confidence = Decimal(str(raw.get("confidence", 0)))
        except (InvalidOperation, TypeError):
            confidence = Decimal("0.0")
        confidence = max(Decimal("0"), min(Decimal("1"), confidence))

        return IntentResult(
            intent=intent,
            confidence=confidence,
            reasoning=str(raw.get("reasoning", "")),
        )
