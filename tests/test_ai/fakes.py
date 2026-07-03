"""Testlar uchun soxta (fake) LLM client — haqiqiy API chaqirilmaydi."""

from __future__ import annotations

import json
from collections import deque
from typing import Any

from app.services.ai.client import LLMClient


class FakeLLMClient(LLMClient):
    """
    Oldindan belgilangan javoblar navbatini (queue) qaytaradi.

    Ishlatish:
        client = FakeLLMClient([{"intent": "create_transaction", ...}])
        result = await client.complete_json(system="...", user="...")
    """

    def __init__(self, responses: list[dict[str, Any] | str] | None = None) -> None:
        self._responses: deque = deque(responses or [])
        self.calls: list[dict[str, Any]] = []

    def queue(self, response: dict[str, Any] | str) -> None:
        self._responses.append(response)

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        image_base64: str | None = None,
        image_media_type: str = "image/jpeg",
    ) -> str:
        self.calls.append({"system": system, "user": user, "image_base64": image_base64})

        if not self._responses:
            return "{}"

        response = self._responses.popleft()
        if isinstance(response, str):
            return response
        return json.dumps(response, ensure_ascii=False)
