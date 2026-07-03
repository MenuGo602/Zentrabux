from loguru import logger


class AuditService:
    @staticmethod
    async def log(action: str, company_id, user_id, data: dict) -> None:
        logger.info(f"AUDIT | {action} | company={company_id} | user={user_id} | {data}")
        # TODO: Bazaga yozish (keyingi bosqich)
