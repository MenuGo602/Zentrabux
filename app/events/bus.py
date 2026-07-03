"""
Event Bus — Zentra'ning asosiy xabardorlik tizimi.

Har bir muhim operatsiya event chiqaradi:
    TransactionCreated → Notification, AI Memory, Reports, Tax, Audit

Bu arxitektura modullarga bir-birini bilmasdan ishlash imkonini beradi.
"""

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from loguru import logger


# ─── Event Types ─────────────────────────────────────────────────────────────
class EventType(StrEnum):
    # Transactions
    TRANSACTION_CREATED = "transaction.created"
    TRANSACTION_UPDATED = "transaction.updated"
    TRANSACTION_DELETED = "transaction.deleted"
    TRANSACTION_CONFIRMED = "transaction.confirmed"

    # Debts
    DEBT_CREATED = "debt.created"
    DEBT_PAYMENT_RECEIVED = "debt.payment.received"
    DEBT_OVERDUE = "debt.overdue"

    # Inventory
    INVENTORY_LOW_STOCK = "inventory.low_stock"
    INVENTORY_MOVEMENT = "inventory.movement"

    # Reports
    REPORT_REQUESTED = "report.requested"
    REPORT_READY = "report.ready"

    # AI
    AI_INTENT_DETECTED = "ai.intent.detected"
    AI_MEMORY_UPDATED = "ai.memory.updated"

    # Auth
    USER_LOGGED_IN = "user.logged_in"
    USER_REGISTERED = "user.registered"

    # Company
    COMPANY_CREATED = "company.created"
    USER_INVITED = "company.user.invited"

    # Counterparties
    CUSTOMER_CREATED = "customer.created"
    SUPPLIER_CREATED = "supplier.created"


# ─── Event Payload ───────────────────────────────────────────────────────────
@dataclass
class Event:
    type: EventType
    company_id: UUID
    user_id: UUID | None
    data: dict[str, Any]
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"Event({self.type}, company={self.company_id})"


# ─── Handler Type ────────────────────────────────────────────────────────────
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


# ─── Event Bus ───────────────────────────────────────────────────────────────
class EventBus:
    """
    In-process async event bus.

    Ishlatish:
        bus = EventBus()

        @bus.on(EventType.TRANSACTION_CREATED)
        async def handle(event: Event):
            await send_notification(event.data)

        await bus.emit(Event(
            type=EventType.TRANSACTION_CREATED,
            company_id=company_id,
            user_id=user_id,
            data={"amount": 100000, "description": "Sotuv"}
        ))
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)

    def on(self, *event_types: EventType) -> Callable:
        """Decorator: handler ro'yxatdan o'tkazadi"""
        def decorator(func: EventHandler) -> EventHandler:
            for event_type in event_types:
                self._handlers[event_type].append(func)
                logger.debug(f"Handler ro'yxatdan o'tdi: {func.__name__} → {event_type}")
            return func
        return decorator

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Programmatic subscription"""
        self._handlers[event_type].append(handler)

    async def emit(self, event: Event) -> None:
        """Event chiqaradi va barcha handlerlarni chaqiradi"""
        handlers = self._handlers.get(event.type, [])

        if not handlers:
            logger.debug(f"Handler topilmadi: {event.type}")
            return

        logger.info(f"Event: {event.type} | Handlers: {len(handlers)}")

        # Barcha handlerlarni parallel ishga tushiramiz
        results = await asyncio.gather(
            *[self._safe_call(handler, event) for handler in handlers],
            return_exceptions=True,
        )

        # Xatolarni loglash (lekin to'xtatmaymiz)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Handler xatosi [{handlers[i].__name__}] "
                    f"event={event.type}: {result}"
                )

    async def _safe_call(self, handler: EventHandler, event: Event) -> None:
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"Event handler xatosi: {handler.__name__} — {e}")
            raise


# ─── Global Instance ─────────────────────────────────────────────────────────
event_bus = EventBus()
