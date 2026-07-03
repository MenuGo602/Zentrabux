"""
Bot Session Store — har bir Telegram foydalanuvchisi uchun
JWT tokenlar va joriy tanlangan kompaniyani Redis'da saqlaydi.

Nega Redis: bot konteyneri qayta ishga tushganda (deploy, crash)
foydalanuvchilar qayta /start bosishga majbur bo'lmasligi kerak —
access/refresh tokenlar saqlanib qoladi.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import redis.asyncio as aioredis
from loguru import logger

from app.core.config import settings

SESSION_KEY_PREFIX = "bot:session:"
AI_SESSION_KEY_PREFIX = "bot:ai_session:"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 60  # 60 kun (refresh token muddatiga yaqin)


@dataclass
class BotSession:
    telegram_id: int
    user_id: str
    access_token: str
    refresh_token: str
    language: str = "uz"
    active_company_id: str | None = None
    active_company_name: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "BotSession":
        return cls(**json.loads(raw))


class SessionStore:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def _client(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    async def get(self, telegram_id: int) -> BotSession | None:
        client = await self._client()
        raw = await client.get(f"{SESSION_KEY_PREFIX}{telegram_id}")
        if not raw:
            return None
        try:
            return BotSession.from_json(raw)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Sessiya buzilgan, o'chirilmoqda: telegram_id={telegram_id} | {e}")
            await self.delete(telegram_id)
            return None

    async def set(self, session: BotSession) -> None:
        client = await self._client()
        await client.set(
            f"{SESSION_KEY_PREFIX}{session.telegram_id}",
            session.to_json(),
            ex=SESSION_TTL_SECONDS,
        )

    async def delete(self, telegram_id: int) -> None:
        client = await self._client()
        await client.delete(f"{SESSION_KEY_PREFIX}{telegram_id}")

    # ─── AI suhbat sessiyasi (session_id) ────────────────────────────────────
    # Har bir kompaniya uchun alohida — foydalanuvchi kompaniya almashtirsa,
    # AI suhbat konteksti aralashib ketmasligi kerak.
    async def get_ai_session_id(self, telegram_id: int, company_id: str) -> str | None:
        client = await self._client()
        return await client.get(f"{AI_SESSION_KEY_PREFIX}{telegram_id}:{company_id}")

    async def set_ai_session_id(self, telegram_id: int, company_id: str, session_id: str) -> None:
        client = await self._client()
        await client.set(
            f"{AI_SESSION_KEY_PREFIX}{telegram_id}:{company_id}",
            session_id,
            ex=60 * 60 * 6,  # 6 soat — uzoq turgan suhbat eskiradi, yangisi boshlanadi
        )

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.close()


session_store = SessionStore()
