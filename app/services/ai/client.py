"""
LLM Client — provayder-agnostik AI chaqiruv qatlami.

Nega abstraksiya kerak:
    - README'da aytilganidek: "OpenAI GPT-4o-mini (almashtirish mumkin)"
    - Ikkala SDK (`openai`, `anthropic`) pyproject.toml'da allaqachon bor
    - Testlarda haqiqiy API chaqirilmasligi kerak — shuning uchun
      barcha yuqori darajadagi servislar (`intent.py`, `extraction.py`, ...)
      `LLMClient` interfeysiga qarab ishlaydi, FakeLLMClient bilan
      osongina almashtiriladi.

Ishlatish:
    client = get_ai_client()
    text = await client.complete_json(system="...", user="...")
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from loguru import logger

from app.core.config import settings


class AIClientError(Exception):
    """LLM chaqiruvi muvaffaqiyatsiz tugaganda ko'tariladi."""


class LLMClient(ABC):
    """Barcha AI provayderlar shu interfeysni amalga oshiradi."""

    @abstractmethod
    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        image_base64: str | None = None,
        image_media_type: str = "image/jpeg",
    ) -> str:
        """Erkin matn javobini qaytaradi."""
        ...

    async def complete_json(
        self,
        system: str,
        user: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        image_base64: str | None = None,
        image_media_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        """
        Strukturalangan (JSON) javob qaytaradi.

        System promptga "faqat JSON qaytar" qoidasi qo'shiladi, javob esa
        xavfsiz tarzda parse qilinadi (``` qurshovlar olib tashlanadi).
        """
        json_system = (
            f"{system}\n\n"
            "MUHIM: Javobni FAQAT va FAQAT JSON formatida qaytar. "
            "Hech qanday kirish so'zi, izoh yoki Markdown qurshovi (```) bo'lmasin. "
            "Javob to'g'ridan-to'g'ri '{' bilan boshlanishi shart."
        )
        raw = await self.complete(
            system=json_system,
            user=user,
            max_tokens=max_tokens,
            temperature=temperature,
            image_base64=image_base64,
            image_media_type=image_media_type,
        )
        return self._parse_json(raw)

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Ba'zan model JSON atrofida ortiqcha matn qoldiradi — birinchi
            # va oxirgi qavslar orasidagi qismni ajratib qayta urinib ko'ramiz.
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    pass
            logger.error(f"AI javobi JSON emas: {raw[:300]}")
            raise AIClientError(f"AI javobini parse qilib bo'lmadi: {e}") from e


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        image_base64: str | None = None,
        image_media_type: str = "image/jpeg",
    ) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self._api_key)

        user_content: Any
        if image_base64:
            user_content = [
                {"type": "text", "text": user},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{image_media_type};base64,{image_base64}"},
                },
            ]
        else:
            user_content = user

        try:
            response = await client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens or settings.AI_MAX_TOKENS,
                temperature=temperature if temperature is not None else settings.AI_TEMPERATURE,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
            )
        except Exception as e:  # noqa: BLE001 — provayder xatosini birxillashtiramiz
            logger.error(f"OpenAI chaqiruvi xato: {e}")
            raise AIClientError(str(e)) from e

        content = response.choices[0].message.content
        if not content:
            raise AIClientError("OpenAI bo'sh javob qaytardi")
        return content


class AnthropicClient(LLMClient):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self._api_key = api_key
        self._model = model

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        image_base64: str | None = None,
        image_media_type: str = "image/jpeg",
    ) -> str:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self._api_key)

        user_content: Any
        if image_base64:
            user_content = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image_media_type,
                        "data": image_base64,
                    },
                },
                {"type": "text", "text": user},
            ]
        else:
            user_content = user

        try:
            response = await client.messages.create(
                model=self._model,
                max_tokens=max_tokens or settings.AI_MAX_TOKENS,
                temperature=temperature if temperature is not None else settings.AI_TEMPERATURE,
                system=system,
                messages=[{"role": "user", "content": user_content}],
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"Anthropic chaqiruvi xato: {e}")
            raise AIClientError(str(e)) from e

        text_blocks = [block.text for block in response.content if block.type == "text"]
        if not text_blocks:
            raise AIClientError("Anthropic bo'sh javob qaytardi")
        return "".join(text_blocks)


def get_ai_client() -> LLMClient:
    """
    Sozlamalarga ko'ra mos provayderni tanlaydi.

    Ustuvorlik: OPENAI_API_KEY mavjud bo'lsa → OpenAI (README'dagi default).
    Aks holda ANTHROPIC_API_KEY bo'lsa → Anthropic.
    Hech biri sozlanmagan bo'lsa — aniq xato bilan to'xtaydi (jim
    muvaffaqiyatsizlikdan ko'ra yaxshiroq).
    """
    if settings.OPENAI_API_KEY:
        return OpenAIClient(api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_MODEL)
    if settings.ANTHROPIC_API_KEY:
        return AnthropicClient(api_key=settings.ANTHROPIC_API_KEY)
    raise AIClientError(
        "AI provayder sozlanmagan: OPENAI_API_KEY yoki ANTHROPIC_API_KEY kerak (.env)"
    )
