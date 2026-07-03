from loguru import logger
from app.events.bus import Event, EventType, event_bus

def register_all_handlers() -> None:
    @event_bus.on(EventType.TRANSACTION_CREATED)
    async def handle_audit(event: Event) -> None:
        logger.info(f"AUDIT | {event.type} | {event.data}")

    @event_bus.on(EventType.TRANSACTION_CREATED)
    async def handle_tax(event: Event) -> None:
        from app.tasks.tax_calc import calculate_tax_task
        calculate_tax_task.delay(
            transaction_id=event.data.get("transaction_id"),
            company_id=str(event.company_id),
        )

    @event_bus.on(EventType.REPORT_REQUESTED)
    async def handle_report(event: Event) -> None:
        from app.tasks.reports import generate_company_report_task
        generate_company_report_task.delay(
            company_id=str(event.company_id),
            period_start_iso=event.data.get("period_start"),
            period_end_iso=event.data.get("period_end"),
        )

    @event_bus.on(EventType.DEBT_OVERDUE)
    async def handle_debt_overdue(event: Event) -> None:
        if not event.user_id:
            return
        from app.tasks.notifications import send_notification_task
        send_notification_task.delay(
            company_id=str(event.company_id),
            user_id=str(event.user_id),
            notification_type="overdue_debt",
            title="⚠️ Muddati o'tgan qarz",
            message=event.data.get("message", "Sizda muddati o'tgan qarz mavjud."),
            data=event.data,
        )

    @event_bus.on(EventType.AI_MEMORY_UPDATED)
    async def handle_ai_memory_updated(event: Event) -> None:
        logger.debug(f"AI Memory yangilandi | company={event.company_id} | {event.data}")

    logger.info("✅ Event handlers ulandi")

