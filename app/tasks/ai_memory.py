"""
AI Memory background task'lari.

AI Memory vaqt o'tishi bilan "chirkinlashishi" mumkin — masalan,
foydalanuvchi endi ishlatmaydigan bir martalik naqshlar. Bu task'lar
xotirani toza va foydali saqlaydi:

    - ``decay_stale_memories``: uzoq vaqt ishlatilmagan past-ishonchli
      xotiralarning confidence darajasini asta pasaytiradi, juda past
      bo'lib qolganlarini o'chiradi.
    - ``expire_memories``: ``expires_at`` muddati o'tgan xotiralarni
      tozalaydi (masalan, mavsumiy naqshlar).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from loguru import logger

from app.tasks.celery_app import celery_app

# Shu muddatdan beri ishlatilmagan xotiralar "eskirgan" hisoblanadi.
STALE_THRESHOLD_DAYS = 90
# Har bir decay siklida confidence shuncha kamayadi.
DECAY_STEP = Decimal("0.1")
# Confidence shu darajadan pastga tushsa, xotira butunlay o'chiriladi.
MIN_CONFIDENCE_THRESHOLD = Decimal("0.1")


@celery_app.task(name="ai_memory.decay_stale_memories")
def decay_stale_memories() -> dict:
    """Uzoq ishlatilmagan xotiralarni asta zaiflashtiradi va juda zaiflarini o'chiradi."""
    import asyncio

    return asyncio.run(_decay_stale_memories_async())


@celery_app.task(name="ai_memory.expire_memories")
def expire_memories() -> dict:
    """``expires_at`` muddati o'tgan xotiralarni o'chiradi."""
    import asyncio

    return asyncio.run(_expire_memories_async())


async def _decay_stale_memories_async() -> dict:
    from sqlalchemy import select

    from app.core.database import AsyncSessionFactory
    from app.models.all_models import AIMemory

    decayed = 0
    deleted = 0

    async with AsyncSessionFactory() as db:
        threshold = datetime.now(UTC) - timedelta(days=STALE_THRESHOLD_DAYS)
        result = await db.execute(select(AIMemory).where(AIMemory.last_used < threshold))
        stale_memories = list(result.scalars().all())

        for memory in stale_memories:
            memory.confidence = memory.confidence - DECAY_STEP
            if memory.confidence <= MIN_CONFIDENCE_THRESHOLD:
                await db.delete(memory)
                deleted += 1
            else:
                decayed += 1

        await db.commit()

    logger.info(f"🧠 AI Memory decay: {decayed} zaiflashtirildi, {deleted} o'chirildi")
    return {"decayed": decayed, "deleted": deleted}


async def _expire_memories_async() -> dict:
    from sqlalchemy import select

    from app.core.database import AsyncSessionFactory
    from app.models.all_models import AIMemory

    async with AsyncSessionFactory() as db:
        now = datetime.now(UTC)
        result = await db.execute(
            select(AIMemory).where(AIMemory.expires_at.is_not(None), AIMemory.expires_at < now)
        )
        expired_memories = list(result.scalars().all())

        for memory in expired_memories:
            await db.delete(memory)

        await db.commit()

    logger.info(f"🧠 AI Memory expiry: {len(expired_memories)} muddati o'tgan xotira o'chirildi")
    return {"expired": len(expired_memories)}
