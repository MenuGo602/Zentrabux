"""
AI Orchestrator — butun AI pipeline'ni boshqaradi.

Oqim:
    Foydalanuvchi xabari
        → AIConversation'ga yoziladi
        → Intent Detection
        → (intentga qarab) Entity Extraction / AI Memory
        → AccountingEngine / TaxEngine / DB so'rovlari (HECH QACHON AI emas!)
        → Response Generator
        → AIConversation'ga assistant javobi yoziladi
        → AIResponse qaytariladi

AI hech qachon to'g'ridan-to'g'ri jurnal yozuvi yoki soliq summasi
yaratmaydi — faqat niyat va ma'lumotlarni aniqlaydi, qolganini
deterministik Engine'lar bajaradi (README'dagi asosiy prinsip).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.accounting.engine import AccountingEngine, AccountingEntry, PaymentMethod, TxType
from app.engines.report.pnl import ProfitAndLossEngine
from app.engines.tax.uzbekistan import UzbekistanTaxEngine
from app.events.bus import Event, EventType, event_bus
from app.models.all_models import Account, AIConversation, Company, Debt, DebtType
from app.services.ai.client import LLMClient
from app.services.ai.extraction import EntityExtractionService
from app.services.ai.intent import IntentDetectionService
from app.services.ai.memory import AIMemoryService
from app.services.ai.response import ResponseGenerator
from app.services.ai.schemas import AIResponse, ExtractedTransaction, Intent
from app.services.debt import DebtService, DebtServiceError

# Shu chegaradan past ishonch bilan aniqlangan intentlar uchun AI
# avtomatik harakat qilmaydi — foydalanuvchidan aniqlashtirish so'raydi.
MIN_INTENT_CONFIDENCE = Decimal("0.45")
CASH_ACCOUNT_CODES = ("5110", "5120", "5210", "5220", "5510")


class AIOrchestrator:
    def __init__(
        self,
        llm_client: LLMClient | None = None,
        accounting_engine: AccountingEngine | None = None,
        debt_service: DebtService | None = None,
    ) -> None:
        self._intent_service = IntentDetectionService(llm_client)
        self._extraction_service = EntityExtractionService(llm_client)
        self._memory_service = AIMemoryService()
        self._response_generator = ResponseGenerator(llm_client)
        self._accounting_engine = accounting_engine or AccountingEngine()
        self._tax_engine = UzbekistanTaxEngine()
        self._pnl_engine = ProfitAndLossEngine()
        self._debt_service = debt_service or DebtService(self._accounting_engine)

    # ─── Asosiy kirish nuqtasi ───────────────────────────────────────────────
    async def process_message(
        self,
        company_id: str,
        user_id: str,
        message: str,
        db: AsyncSession,
        session_id: str | None = None,
    ) -> AIResponse:
        session_id = session_id or str(uuid4())

        await self._save_message(company_id, user_id, session_id, "user", message, db)

        intent_result = await self._intent_service.detect(message)
        logger.info(f"AI intent: {intent_result.intent} (confidence={intent_result.confidence})")

        if intent_result.confidence < MIN_INTENT_CONFIDENCE:
            response = AIResponse(
                intent=Intent.UNKNOWN,
                message=(
                    "Kechirasiz, tushunmadim. Tranzaksiya kiritish, balansni so'rash, "
                    "qarzlarni tekshirish yoki hisobot so'rash mumkin — qaytadan yozib ko'ring."
                ),
                requires_clarification=True,
                session_id=session_id,
            )
        else:
            handler = self._HANDLERS.get(intent_result.intent, AIOrchestrator._handle_smalltalk)
            response = await handler(self, company_id, user_id, message, db)
            response.session_id = session_id

        await self._save_message(
            company_id, user_id, session_id, "assistant", response.message, db,
            intent=intent_result.intent,
        )
        await event_bus.emit(Event(
            type=EventType.AI_INTENT_DETECTED,
            company_id=_as_uuid(company_id),
            user_id=_as_uuid(user_id),
            data={"intent": intent_result.intent, "confidence": float(intent_result.confidence)},
        ))

        return response

    # ─── Intent: create_transaction ──────────────────────────────────────────
    async def _handle_create_transaction(
        self, company_id: str, user_id: str, message: str, db: AsyncSession
    ) -> AIResponse:
        extracted = await self._extraction_service.extract_transaction(message)

        if extracted.missing_fields:
            return AIResponse(
                intent=Intent.CREATE_TRANSACTION,
                message=self._ask_for_missing_fields(extracted),
                requires_clarification=True,
                data={"partial": extracted.model_dump(mode="json")},
            )

        # AI Memory: kontragent bo'yicha o'rgangan kategoriya bo'lsa, taklif qilamiz
        # (lekin foydalanuvchi/AI aniq kategoriya aytgan bo'lsa, ustunlik o'shanga beriladi)
        if not extracted.category_hint and extracted.counterparty_name:
            suggested = await self._memory_service.suggest_category(
                company_id, user_id, extracted.counterparty_name, db
            )
            if suggested:
                extracted.category_hint = suggested

        payment_method = (
            PaymentMethod(extracted.payment_method) if extracted.payment_method else PaymentMethod.CASH
        )

        try:
            tx_type = TxType(extracted.transaction_type)
        except ValueError:
            return AIResponse(
                intent=Intent.CREATE_TRANSACTION,
                message=f"Tranzaksiya turini aniqlay olmadim: {extracted.transaction_type!r}",
                requires_clarification=True,
            )

        entry = AccountingEntry(
            transaction_type=tx_type,
            amount=extracted.amount,
            description=extracted.description or message[:255],
            transaction_date=extracted.transaction_date or date.today(),
            currency=extracted.currency,
            payment_method=payment_method,
            is_credit=extracted.is_credit,
            notes=f"AI orqali yaratildi: \"{message}\"",
            ai_generated=True,
            ai_confidence=extracted.confidence,
        )

        try:
            tx_result = await self._accounting_engine.process(
                entry=entry, company_id=company_id, user_id=user_id, db=db
            )
        except ValueError as e:
            return AIResponse(
                intent=Intent.CREATE_TRANSACTION,
                message=f"Tranzaksiyani yaratib bo'lmadi: {e}",
                data={"error": str(e)},
            )

        if extracted.counterparty_name and extracted.category_hint:
            await self._memory_service.remember_category_pattern(
                company_id, user_id, extracted.counterparty_name, extracted.category_hint, db
            )
            await event_bus.emit(Event(
                type=EventType.AI_MEMORY_UPDATED,
                company_id=_as_uuid(company_id),
                user_id=_as_uuid(user_id),
                data={"counterparty": extracted.counterparty_name, "category": extracted.category_hint},
            ))

        await event_bus.emit(Event(
            type=EventType.TRANSACTION_CREATED,
            company_id=_as_uuid(company_id),
            user_id=_as_uuid(user_id),
            data={
                "transaction_id": tx_result["id"],
                "amount": float(extracted.amount),
                "type": extracted.transaction_type,
                "description": entry.description,
            },
        ))

        message_text = await self._response_generator.generate("create_transaction", tx_result)
        return AIResponse(
            intent=Intent.CREATE_TRANSACTION,
            message=message_text,
            transaction=tx_result,
            data={"extracted_confidence": float(extracted.confidence)},
        )

    @staticmethod
    def _ask_for_missing_fields(extracted: ExtractedTransaction) -> str:
        prompts = {
            "amount": "qancha summada",
            "transaction_type": "bu kirimmi yoki chiqimmi",
        }
        asks = [prompts.get(f, f) for f in extracted.missing_fields]
        return f"Iltimos, aniqroq yozing — {', '.join(asks)} ekanini bilmadim."

    # ─── Intent: record_debt_payment ─────────────────────────────────────────
    async def _handle_record_debt_payment(
        self, company_id: str, user_id: str, message: str, db: AsyncSession
    ) -> AIResponse:
        extracted = await self._extraction_service.extract_debt_payment(message)

        if extracted.missing_fields:
            return AIResponse(
                intent=Intent.RECORD_DEBT_PAYMENT,
                message="Iltimos, kimning qarzi va qancha to'langanini aniqroq yozing.",
                requires_clarification=True,
                data={"partial": extracted.model_dump(mode="json")},
            )

        debt = await self._debt_service.find_open_debt_by_counterparty_name(
            company_id, extracted.counterparty_name, db
        )
        if not debt:
            return AIResponse(
                intent=Intent.RECORD_DEBT_PAYMENT,
                message=f"\"{extracted.counterparty_name}\" nomli ochiq qarz topilmadi.",
            )

        try:
            result = await self._debt_service.record_payment(
                debt=debt,
                amount=extracted.amount,
                company_id=company_id,
                user_id=user_id,
                db=db,
                payment_date=extracted.payment_date or date.today(),
            )
        except DebtServiceError as e:
            return AIResponse(intent=Intent.RECORD_DEBT_PAYMENT, message=str(e), data={"error": str(e)})

        await event_bus.emit(Event(
            type=EventType.DEBT_PAYMENT_RECEIVED,
            company_id=_as_uuid(company_id),
            user_id=_as_uuid(user_id),
            data=result,
        ))

        message_text = await self._response_generator.generate("record_debt_payment", result)
        return AIResponse(intent=Intent.RECORD_DEBT_PAYMENT, message=message_text, data=result)

    # ─── Intent: query_balance ────────────────────────────────────────────────
    async def _handle_query_balance(
        self, company_id: str, user_id: str, message: str, db: AsyncSession
    ) -> AIResponse:
        result = await db.execute(
            select(Account).where(
                Account.company_id == company_id,
                Account.code.in_(CASH_ACCOUNT_CODES),
            )
        )
        accounts = result.scalars().all()
        balances = [
            {"code": acc.code, "name": acc.name, "balance": float(acc.balance), "currency": acc.currency}
            for acc in accounts
        ]
        total = sum((acc.balance for acc in accounts), Decimal("0"))

        message_text = await self._response_generator.generate(
            "query_balance", {"accounts": balances, "total": float(total)}
        )
        return AIResponse(
            intent=Intent.QUERY_BALANCE,
            message=message_text,
            data={"accounts": balances, "total": float(total)},
        )

    # ─── Intent: query_debt ────────────────────────────────────────────────
    async def _handle_query_debt(
        self, company_id: str, user_id: str, message: str, db: AsyncSession
    ) -> AIResponse:
        result = await db.execute(
            select(Debt).where(
                Debt.company_id == company_id,
                Debt.status.in_(["active", "partially_paid", "overdue"]),
            ).order_by(Debt.due_date.asc().nulls_last())
        )
        debts = result.scalars().all()

        receivable_total = sum(
            (d.remaining_amount for d in debts if d.debt_type == DebtType.RECEIVABLE), Decimal("0")
        )
        payable_total = sum(
            (d.remaining_amount for d in debts if d.debt_type == DebtType.PAYABLE), Decimal("0")
        )

        summary = {
            "receivable_total": float(receivable_total),
            "payable_total": float(payable_total),
            "open_debts_count": len(debts),
            "debts": [
                {
                    "id": str(d.id),
                    "type": d.debt_type,
                    "description": d.description,
                    "remaining_amount": float(d.remaining_amount),
                    "due_date": str(d.due_date) if d.due_date else None,
                }
                for d in debts[:10]
            ],
        }

        message_text = await self._response_generator.generate("query_debt", summary)
        return AIResponse(intent=Intent.QUERY_DEBT, message=message_text, data=summary)

    # ─── Intent: query_report ────────────────────────────────────────────────
    async def _handle_query_report(
        self, company_id: str, user_id: str, message: str, db: AsyncSession
    ) -> AIResponse:
        today = date.today()
        period_start = today.replace(day=1)

        pnl = await self._pnl_engine.generate(company_id, db, period_start, today)
        message_text = await self._response_generator.generate("query_report", pnl.to_dict())
        return AIResponse(intent=Intent.QUERY_REPORT, message=message_text, data=pnl.to_dict())

    # ─── Intent: query_tax ────────────────────────────────────────────────
    async def _handle_query_tax(
        self, company_id: str, user_id: str, message: str, db: AsyncSession
    ) -> AIResponse:
        today = date.today()
        period_start = today.replace(day=1)

        company_result = await db.execute(select(Company).where(Company.id == company_id))
        company = company_result.scalar_one_or_none()
        is_vat_payer = bool(company and company.tax_regime == "QQS")

        pnl = await self._pnl_engine.generate(company_id, db, period_start, today)
        vat_result = await self._tax_engine.calculate_vat(
            taxable_amount=pnl.total_income, company_id=company_id, is_vat_payer=is_vat_payer
        )
        profit_tax_result = await self._tax_engine.calculate_profit_tax(
            net_profit=pnl.net_profit, company_id=company_id
        )

        summary = {
            "revenue": float(pnl.total_income),
            "net_profit": float(pnl.net_profit),
            "vat": vat_result.to_dict() if vat_result else None,
            "profit_tax": profit_tax_result.to_dict() if profit_tax_result else None,
        }
        message_text = await self._response_generator.generate("query_tax", summary)
        return AIResponse(intent=Intent.QUERY_TAX, message=message_text, data=summary)

    # ─── Intent: smalltalk / unknown ─────────────────────────────────────────
    async def _handle_smalltalk(
        self, company_id: str, user_id: str, message: str, db: AsyncSession
    ) -> AIResponse:
        message_text = await self._response_generator.generate("smalltalk", {"user_message": message})
        return AIResponse(intent=Intent.SMALLTALK, message=message_text)

    _HANDLERS = {
        Intent.CREATE_TRANSACTION: _handle_create_transaction,
        Intent.RECORD_DEBT_PAYMENT: _handle_record_debt_payment,
        Intent.QUERY_BALANCE: _handle_query_balance,
        Intent.QUERY_DEBT: _handle_query_debt,
        Intent.QUERY_REPORT: _handle_query_report,
        Intent.QUERY_TAX: _handle_query_tax,
        Intent.SMALLTALK: _handle_smalltalk,
    }

    # ─── Yordamchi ────────────────────────────────────────────────────────────
    async def _save_message(
        self,
        company_id: str,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        db: AsyncSession,
        intent: str | None = None,
    ) -> None:
        db.add(AIConversation(
            company_id=company_id,
            user_id=user_id,
            session_id=session_id,
            message_role=role,
            content=content,
            intent=intent,
        ))
        await db.flush()


def _as_uuid(value):
    from uuid import UUID

    return value if isinstance(value, UUID) else UUID(str(value))
