import asyncio
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import Base
from app.engines.accounting.chart_of_accounts import bootstrap_company_accounts
from app.models.all_models import Company


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Har bir test uchun toza in-memory holatga yaqin test bazasi"""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def test_company(db_session: AsyncSession) -> Company:
    """Test uchun kompaniya + standart Chart of Accounts"""
    company = Company(name="Test MCHJ", country_code="UZB", currency="UZS")
    db_session.add(company)
    await db_session.flush()

    await bootstrap_company_accounts(str(company.id), db_session)
    await db_session.flush()

    return company
