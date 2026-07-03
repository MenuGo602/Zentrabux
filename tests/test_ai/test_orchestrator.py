from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.all_models import Company, Customer, Debt, DebtStatus, DebtType, User
from app.services.ai.orchestrator import AIOrchestrator
from app.services.ai.schemas import Intent
from tests.test_ai.fakes import FakeLLMClient


async def _make_user(db: AsyncSession) -> User:
    user = User(full_name="Test Foydalanuvchi", phone="+998901112233")
    db.add(user)
    await db.flush()
    return user


class TestCreateTransactionFlow:
    async def test_full_flow_creates_transaction(
        self, db_session: AsyncSession, test_company: Company
    ):
        user = await _make_user(db_session)
        client = FakeLLMClient([
            {"intent": "create_transaction", "confidence": 0.92, "reasoning": "sotuv"},
            {
                "transaction_type": "income",
                "amount": 250000,
                "currency": "UZS",
                "description": "Tovar sotuvi",
                "category_hint": None,
                "counterparty_name": None,
                "payment_method": "cash",
                "is_credit": False,
                "transaction_date": None,
                "confidence": 0.9,
                "missing_fields": [],
            },
            "✅ 250 000 so'm miqdorida tranzaksiya yozildi.",
        ])
        orchestrator = AIOrchestrator(llm_client=client)

        response = await orchestrator.process_message(
            company_id=str(test_company.id),
            user_id=str(user.id),
            message="250 ming so'mga tovar sotdim",
            db=db_session,
        )

        assert response.intent == Intent.CREATE_TRANSACTION
        assert response.transaction is not None
        assert response.transaction["total_amount"] == 250000.0
        assert response.requires_clarification is False

    async def test_low_confidence_intent_requests_clarification_without_side_effects(
        self, db_session: AsyncSession, test_company: Company
    ):
        user = await _make_user(db_session)
        client = FakeLLMClient([
            {"intent": "create_transaction", "confidence": 0.2, "reasoning": "noaniq"},
        ])
        orchestrator = AIOrchestrator(llm_client=client)

        response = await orchestrator.process_message(
            company_id=str(test_company.id),
            user_id=str(user.id),
            message="nimadir",
            db=db_session,
        )

        assert response.requires_clarification is True
        assert response.transaction is None
        # Faqat intent detection chaqirilgan — extraction yoki response generation yo'q
        assert len(client.calls) == 1

    async def test_missing_amount_requests_clarification_without_creating_transaction(
        self, db_session: AsyncSession, test_company: Company
    ):
        user = await _make_user(db_session)
        client = FakeLLMClient([
            {"intent": "create_transaction", "confidence": 0.9},
            {
                "transaction_type": "expense",
                "amount": None,
                "confidence": 0.5,
                "missing_fields": ["amount"],
            },
        ])
        orchestrator = AIOrchestrator(llm_client=client)

        response = await orchestrator.process_message(
            company_id=str(test_company.id),
            user_id=str(user.id),
            message="xarajat qildim",
            db=db_session,
        )

        assert response.requires_clarification is True
        assert response.transaction is None


class TestQueryBalanceFlow:
    async def test_query_balance_returns_zero_for_new_company(
        self, db_session: AsyncSession, test_company: Company
    ):
        user = await _make_user(db_session)
        client = FakeLLMClient([
            {"intent": "query_balance", "confidence": 0.88},
            "Hozircha kassangizda mablag' yo'q.",
        ])
        orchestrator = AIOrchestrator(llm_client=client)

        response = await orchestrator.process_message(
            company_id=str(test_company.id),
            user_id=str(user.id),
            message="kassada qancha pul bor?",
            db=db_session,
        )

        assert response.intent == Intent.QUERY_BALANCE
        assert response.data["total"] == 0.0


class TestRecordDebtPaymentFlow:
    async def test_records_payment_against_existing_receivable(
        self, db_session: AsyncSession, test_company: Company
    ):
        user = await _make_user(db_session)
        customer = Customer(company_id=test_company.id, name="Aziz Karimov")
        db_session.add(customer)
        await db_session.flush()

        debt = Debt(
            company_id=test_company.id,
            debt_type=DebtType.RECEIVABLE,
            counterparty_type="customer",
            customer_id=customer.id,
            description="Tovar qarzga sotildi",
            original_amount=Decimal("500000"),
            paid_amount=Decimal("0"),
            remaining_amount=Decimal("500000"),
            status=DebtStatus.ACTIVE,
        )
        db_session.add(debt)
        await db_session.flush()

        client = FakeLLMClient([
            {"intent": "record_debt_payment", "confidence": 0.91},
            {
                "counterparty_name": "Aziz Karimov",
                "amount": 200000,
                "payment_date": str(date.today()),
                "confidence": 0.85,
                "missing_fields": [],
            },
            "Aziz Karimovning 200 000 so'mlik to'lovi qabul qilindi.",
        ])
        orchestrator = AIOrchestrator(llm_client=client)

        response = await orchestrator.process_message(
            company_id=str(test_company.id),
            user_id=str(user.id),
            message="Aziz 200 ming to'ladi",
            db=db_session,
        )

        assert response.intent == Intent.RECORD_DEBT_PAYMENT
        assert response.data["remaining_amount"] == 300000.0
        assert debt.status == DebtStatus.PARTIALLY_PAID

    async def test_no_matching_debt_returns_friendly_message(
        self, db_session: AsyncSession, test_company: Company
    ):
        user = await _make_user(db_session)
        client = FakeLLMClient([
            {"intent": "record_debt_payment", "confidence": 0.9},
            {
                "counterparty_name": "Notanish Odam",
                "amount": 100000,
                "confidence": 0.7,
                "missing_fields": [],
            },
        ])
        orchestrator = AIOrchestrator(llm_client=client)

        response = await orchestrator.process_message(
            company_id=str(test_company.id),
            user_id=str(user.id),
            message="Notanish Odam to'ladi",
            db=db_session,
        )

        assert "topilmadi" in response.message
