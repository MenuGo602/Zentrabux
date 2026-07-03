from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.accounting.chart_of_accounts import (
    STANDARD_ACCOUNTS,
    bootstrap_company_accounts,
)
from app.models.all_models import Account, Company


class TestChartOfAccounts:
    async def test_bootstrap_creates_all_accounts(
        self, db_session: AsyncSession
    ):
        company = Company(name="Yangi MCHJ", country_code="UZB")
        db_session.add(company)
        await db_session.flush()

        created_count = await bootstrap_company_accounts(str(company.id), db_session)

        assert created_count == len(STANDARD_ACCOUNTS)

        result = await db_session.execute(
            select(Account).where(Account.company_id == company.id)
        )
        accounts = result.scalars().all()
        assert len(accounts) == len(STANDARD_ACCOUNTS)

    async def test_bootstrap_is_idempotent(self, db_session: AsyncSession):
        """Ikkinchi marta chaqirilsa, qayta yaratmasligi kerak"""
        company = Company(name="Test", country_code="UZB")
        db_session.add(company)
        await db_session.flush()

        first_run = await bootstrap_company_accounts(str(company.id), db_session)
        second_run = await bootstrap_company_accounts(str(company.id), db_session)

        assert first_run == len(STANDARD_ACCOUNTS)
        assert second_run == 0  # Hech narsa qo'shilmadi

    async def test_essential_accounts_exist(self, test_company: Company):
        codes = {acc.code for acc in STANDARD_ACCOUNTS}
        assert "5110" in codes   # Kassa
        assert "9010" in codes   # Daromad
        assert "4010" in codes   # Debitorlik
        assert "6010" in codes   # Kreditorlik
