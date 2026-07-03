"""Response Generator — natijani tabiiy o'zbek tiliga aylantirish."""

from __future__ import annotations

import json
from decimal import Decimal

from loguru import logger

from app.services.ai.client import AIClientError, LLMClient, get_ai_client
from app.services.ai.prompts import RESPONSE_GENERATION_PROMPT


def _json_default(value):
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


class ResponseGenerator:
    """Strukturali natijani (dict) tabiiy tilga o'giradi."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._client = llm_client or get_ai_client()

    async def generate(self, intent: str, result_data: dict) -> str:
        try:
            payload = json.dumps(result_data, ensure_ascii=False, default=_json_default)
        except (TypeError, ValueError):
            payload = str(result_data)

        try:
            return await self._client.complete(
                system=RESPONSE_GENERATION_PROMPT,
                user=f"Niyat: {intent}\nNatija: {payload}",
                temperature=0.3,
            )
        except AIClientError as e:
            logger.error(f"Response generation xato: {e}")
            return self._fallback(intent, result_data)

    @staticmethod
    def _fallback(intent: str, result_data: dict) -> str:
        """AI ishlamasa ham foydalanuvchi javobsiz qolmasligi uchun oddiy shablon."""
        if intent == "create_transaction" and result_data.get("total_amount"):
            return (
                f"✅ {result_data.get('total_amount'):,.0f} {result_data.get('currency', 'UZS')} "
                f"miqdorida tranzaksiya yozildi."
            )
        return "So'rovingiz qabul qilindi."
