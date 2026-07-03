from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.suppliers import (
    SupplierCreate,
    SupplierUpdate,
    create_supplier,
    get_supplier,
    list_suppliers,
    update_supplier,
)
from app.models.all_models import Company, User


def _fake_user() -> User:
    return User(id=uuid4(), full_name="Test Foydalanuvchi", language="uz")


class TestCreateSupplier:
    async def test_creates_supplier_with_default_payment_terms(
        self, db_session: AsyncSession, test_company: Company
    ):
        supplier = await create_supplier(
            test_company.id, SupplierCreate(name="Ta'minotchi MChJ"), _fake_user(), None, db_session
        )

        assert supplier.name == "Ta'minotchi MChJ"
        assert supplier.payment_terms == 30
        assert supplier.current_balance == 0

    async def test_creates_supplier_with_custom_payment_terms(
        self, db_session: AsyncSession, test_company: Company
    ):
        supplier = await create_supplier(
            test_company.id,
            SupplierCreate(name="Tezkor yetkazib beruvchi", payment_terms=7),
            _fake_user(),
            None,
            db_session,
        )
        assert supplier.payment_terms == 7


class TestListAndUpdateSupplier:
    async def test_lists_only_active_suppliers_by_default(
        self, db_session: AsyncSession, test_company: Company
    ):
        supplier = await create_supplier(
            test_company.id, SupplierCreate(name="O'chirilgan"), _fake_user(), None, db_session
        )
        supplier.is_active = False
        await db_session.flush()

        result = await list_suppliers(test_company.id, None, False, _fake_user(), None, db_session)
        assert supplier.id not in [s.id for s in result]

    async def test_get_returns_404_for_unknown_id(self, db_session: AsyncSession, test_company: Company):
        with pytest.raises(Exception):
            await get_supplier(test_company.id, uuid4(), _fake_user(), None, db_session)

    async def test_update_changes_only_provided_fields(
        self, db_session: AsyncSession, test_company: Company
    ):
        supplier = await create_supplier(
            test_company.id, SupplierCreate(name="Eski nom", payment_terms=30), _fake_user(), None, db_session
        )

        updated = await update_supplier(
            test_company.id, supplier.id, SupplierUpdate(payment_terms=15), _fake_user(), None, db_session
        )

        assert updated.payment_terms == 15
        assert updated.name == "Eski nom"
