"""
Customers API testlari.

Diqqat: bu yerda route funksiyalari FastAPI DI zanjirisiz to'g'ridan-to'g'ri
chaqiriladi (repo'dagi boshqa testlar bilan bir xil uslub) — shuning uchun
`current_user`/`membership` uchun FastAPI avtomatik hal qiladigan Depends()
o'rniga qo'lda tayyorlangan obyektlar beriladi. Ruxsat tekshiruvi
(`require_permission`) alohida — `test_permissions.py`da qamrab olinadi deb
taxmin qilinadi; bu yerda faqat CRUD business-mantig'i tekshiriladi.
"""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.customers import (
    CustomerCreate,
    CustomerUpdate,
    create_customer,
    get_customer,
    list_customers,
    update_customer,
)
from app.models.all_models import Company, User


def _fake_user() -> User:
    return User(id=uuid4(), full_name="Test Foydalanuvchi", language="uz")


class TestCreateCustomer:
    async def test_creates_customer_with_defaults(self, db_session: AsyncSession, test_company: Company):
        body = CustomerCreate(name="Aliyev Aziz")
        customer = await create_customer(test_company.id, body, _fake_user(), None, db_session)

        assert customer.name == "Aliyev Aziz"
        assert customer.credit_limit == 0
        assert customer.current_balance == 0
        assert customer.is_active is True

    async def test_creates_customer_with_full_details(self, db_session: AsyncSession, test_company: Company):
        body = CustomerCreate(
            name="Malika MChJ", inn="123456789", phone="+998901234567", credit_limit=5_000_000
        )
        customer = await create_customer(test_company.id, body, _fake_user(), None, db_session)

        assert customer.inn == "123456789"
        assert customer.credit_limit == 5_000_000


class TestListCustomers:
    async def test_lists_only_customers_of_given_company(
        self, db_session: AsyncSession, test_company: Company
    ):
        other_company = Company(name="Boshqa kompaniya", country_code="UZB", currency="UZS")
        db_session.add(other_company)
        await db_session.flush()

        await create_customer(test_company.id, CustomerCreate(name="Mijoz A"), _fake_user(), None, db_session)
        await create_customer(other_company.id, CustomerCreate(name="Mijoz B"), _fake_user(), None, db_session)

        result = await list_customers(test_company.id, None, False, _fake_user(), None, db_session)

        assert len(result) == 1
        assert result[0].name == "Mijoz A"

    async def test_excludes_inactive_by_default(self, db_session: AsyncSession, test_company: Company):
        customer = await create_customer(
            test_company.id, CustomerCreate(name="Faol emas"), _fake_user(), None, db_session
        )
        customer.is_active = False
        await db_session.flush()

        result = await list_customers(test_company.id, None, False, _fake_user(), None, db_session)
        assert customer.id not in [c.id for c in result]

        result_with_inactive = await list_customers(
            test_company.id, None, True, _fake_user(), None, db_session
        )
        assert customer.id in [c.id for c in result_with_inactive]

    async def test_search_filters_by_name(self, db_session: AsyncSession, test_company: Company):
        await create_customer(test_company.id, CustomerCreate(name="Aziz Aliyev"), _fake_user(), None, db_session)
        await create_customer(test_company.id, CustomerCreate(name="Bekzod Yusupov"), _fake_user(), None, db_session)

        result = await list_customers(test_company.id, "aziz", False, _fake_user(), None, db_session)
        assert len(result) == 1
        assert result[0].name == "Aziz Aliyev"


class TestGetAndUpdateCustomer:
    async def test_get_returns_404_for_unknown_id(self, db_session: AsyncSession, test_company: Company):
        with pytest.raises(Exception):
            await get_customer(test_company.id, uuid4(), _fake_user(), None, db_session)

    async def test_update_changes_only_provided_fields(
        self, db_session: AsyncSession, test_company: Company
    ):
        customer = await create_customer(
            test_company.id, CustomerCreate(name="Eski nom", phone="+998900000000"), _fake_user(), None, db_session
        )

        updated = await update_customer(
            test_company.id, customer.id, CustomerUpdate(name="Yangi nom"), _fake_user(), None, db_session
        )

        assert updated.name == "Yangi nom"
        assert updated.phone == "+998900000000"  # o'zgarmagan
