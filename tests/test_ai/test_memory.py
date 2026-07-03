from sqlalchemy.ext.asyncio import AsyncSession

from app.models.all_models import Company, User
from app.services.ai.memory import AIMemoryService


async def _make_user(db: AsyncSession) -> User:
    user = User(full_name="Test Foydalanuvchi", phone="+998900000000")
    db.add(user)
    await db.flush()
    return user


class TestAIMemoryService:
    async def test_first_observation_creates_low_confidence_memory(
        self, db_session: AsyncSession, test_company: Company
    ):
        user = await _make_user(db_session)
        service = AIMemoryService()

        memory = await service.remember_category_pattern(
            str(test_company.id), str(user.id), "Elektr Energiya", "Kommunal xarajatlar", db_session
        )

        assert memory.occurrences == 1
        assert memory.value["category_hint"] == "Kommunal xarajatlar"

    async def test_repeated_observation_increments_occurrences_and_confidence(
        self, db_session: AsyncSession, test_company: Company
    ):
        user = await _make_user(db_session)
        service = AIMemoryService()

        await service.remember_category_pattern(
            str(test_company.id), str(user.id), "Elektr Energiya", "Kommunal xarajatlar", db_session
        )
        memory = await service.remember_category_pattern(
            str(test_company.id), str(user.id), "elektr energiya", "Kommunal xarajatlar", db_session
        )

        assert memory.occurrences == 2

    async def test_suggestion_requires_minimum_occurrences(
        self, db_session: AsyncSession, test_company: Company
    ):
        user = await _make_user(db_session)
        service = AIMemoryService()

        await service.remember_category_pattern(
            str(test_company.id), str(user.id), "Aziz Supplier", "Xom ashyo", db_session
        )
        suggestion = await service.suggest_category(
            str(test_company.id), str(user.id), "Aziz Supplier", db_session
        )

        assert suggestion is None  # faqat 1 marta ko'rilgan — hali taklif qilinmaydi

    async def test_suggestion_returned_after_minimum_occurrences(
        self, db_session: AsyncSession, test_company: Company
    ):
        user = await _make_user(db_session)
        service = AIMemoryService()

        for _ in range(2):
            await service.remember_category_pattern(
                str(test_company.id), str(user.id), "Aziz Supplier", "Xom ashyo", db_session
            )

        suggestion = await service.suggest_category(
            str(test_company.id), str(user.id), "aziz supplier", db_session
        )

        assert suggestion == "Xom ashyo"

    async def test_forget_removes_memory(self, db_session: AsyncSession, test_company: Company):
        user = await _make_user(db_session)
        service = AIMemoryService()

        memory = await service.remember_category_pattern(
            str(test_company.id), str(user.id), "Test", "Boshqa", db_session
        )

        deleted = await service.forget(str(memory.id), db_session)
        memories = await service.list_memories(str(test_company.id), str(user.id), db_session)

        assert deleted is True
        assert memories == []

    async def test_forget_unknown_id_returns_false(
        self, db_session: AsyncSession, test_company: Company
    ):
        service = AIMemoryService()
        import uuid

        deleted = await service.forget(str(uuid.uuid4()), db_session)

        assert deleted is False
