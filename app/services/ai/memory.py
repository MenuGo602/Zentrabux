"""
AI Memory — foydalanuvchi xatti-harakatlarini "eslab qolish".

Misol: agar foydalanuvchi "Elektr energiya" ta'minotchisidan xarid qilganda
doim "Kommunal xarajatlar" kategoriyasini tanlasa, AI Memory buni
``SUPPLIER_PATTERN`` sifatida saqlaydi va keyingi safar AI avtomatik
kategoriya taklif qiladi — lekin HECH QACHON foydalanuvchi tasdiqisiz
yakuniy qarorni o'zgartirmaydi (taklif darajasida qoladi).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.all_models import AIMemory, MemoryType

# Bitta xulosa chiqarish uchun minimal takrorlanish soni — shovqindan
# (bir martalik tasodifdan) himoya qiladi.
MIN_OCCURRENCES_FOR_SUGGESTION = 2


def _normalize_key(value: str) -> str:
    return value.strip().lower()


class AIMemoryService:
    """``ai_memory`` jadvali bilan ishlovchi servis."""

    async def remember_category_pattern(
        self,
        company_id: str,
        user_id: str,
        counterparty_name: str,
        category_hint: str,
        db: AsyncSession,
    ) -> AIMemory:
        """
        Kontragent ↔ kategoriya bog'lanishini eslab qoladi (yoki mavjudini
        yangilaydi — occurrences++, confidence o'sadi).
        """
        key = _normalize_key(counterparty_name)

        result = await db.execute(
            select(AIMemory).where(
                AIMemory.company_id == company_id,
                AIMemory.user_id == user_id,
                AIMemory.memory_type == MemoryType.SUPPLIER_PATTERN,
                AIMemory.key == key,
            )
        )
        memory = result.scalar_one_or_none()

        if memory:
            memory.occurrences += 1
            memory.value = {"category_hint": category_hint}
            memory.confidence = min(Decimal("1.0"), memory.confidence + Decimal("0.1"))
            memory.last_used = datetime.now(UTC)
            logger.debug(f"AI Memory yangilandi: {key} → {category_hint} ({memory.occurrences}x)")
        else:
            memory = AIMemory(
                company_id=company_id,
                user_id=user_id,
                memory_type=MemoryType.SUPPLIER_PATTERN,
                key=key,
                value={"category_hint": category_hint},
                confidence=Decimal("0.5"),
                occurrences=1,
                last_used=datetime.now(UTC),
            )
            db.add(memory)
            logger.debug(f"AI Memory yaratildi: {key} → {category_hint}")

        await db.flush()
        return memory

    async def suggest_category(
        self,
        company_id: str,
        user_id: str,
        counterparty_name: str,
        db: AsyncSession,
    ) -> str | None:
        """
        Avval ko'rilgan kontragent uchun kategoriya taklif qiladi.
        Faqat yetarlicha takrorlangan (``MIN_OCCURRENCES_FOR_SUGGESTION``)
        va muddati o'tmagan xotiralar qaytariladi.
        """
        if not counterparty_name:
            return None

        key = _normalize_key(counterparty_name)
        result = await db.execute(
            select(AIMemory).where(
                AIMemory.company_id == company_id,
                AIMemory.user_id == user_id,
                AIMemory.memory_type == MemoryType.SUPPLIER_PATTERN,
                AIMemory.key == key,
            )
        )
        memory = result.scalar_one_or_none()

        if not memory or memory.occurrences < MIN_OCCURRENCES_FOR_SUGGESTION:
            return None
        if memory.expires_at and memory.expires_at < datetime.now(UTC):
            return None

        return memory.value.get("category_hint")

    async def list_memories(
        self,
        company_id: str,
        user_id: str,
        db: AsyncSession,
        memory_type: MemoryType | None = None,
    ) -> list[AIMemory]:
        filters = [AIMemory.company_id == company_id, AIMemory.user_id == user_id]
        if memory_type:
            filters.append(AIMemory.memory_type == memory_type)

        result = await db.execute(select(AIMemory).where(*filters).order_by(AIMemory.last_used.desc()))
        return list(result.scalars().all())

    async def forget(self, memory_id: str, db: AsyncSession) -> bool:
        """Foydalanuvchi noto'g'ri o'rgangan xotirani o'chirib tashlashi mumkin."""
        result = await db.execute(select(AIMemory).where(AIMemory.id == memory_id))
        memory = result.scalar_one_or_none()
        if not memory:
            return False
        await db.delete(memory)
        await db.flush()
        return True
