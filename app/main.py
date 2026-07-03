"""
Zentra — AI-powered Accounting Platform
API-first arxitektura: Telegram, Web, Mobile bir backenddan foydalanadi.
"""

from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app.core.config import settings
from app.core.database import engine, Base

# Routers
from app.api.v1 import auth, companies, transactions, accounts, reports, debts, ai, tax, documents, customers, suppliers


# ─── Lifespan ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ilova ishga tushganda va to'xtaganda bajariladigan amallar"""
    logger.info(f"🚀 Zentra API ishga tushmoqda... [{settings.ENVIRONMENT}]")

    # Sentry (production uchun)
    if settings.SENTRY_DSN and settings.is_production:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[FastApiIntegration()],
            traces_sample_rate=0.1,
        )
        logger.info("✅ Sentry ulandi")

    # Event handlerlarni ro'yxatdan o'tkazish
    from app.events import register_all_handlers
    register_all_handlers()
    logger.info("✅ Event handlers ro'yxatdan o'tdi")

    yield

    logger.info("🛑 Zentra API to'xtatilmoqda...")
    await engine.dispose()


# ─── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Zentra API",
    description="AI-powered accounting platform for Central Asia",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)


# ─── Middleware ───────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Exception Handlers ──────────────────────────────────────────────────────
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError):
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc)},
    )


# ─── Routers ─────────────────────────────────────────────────────────────────
PREFIX = settings.API_V1_PREFIX

app.include_router(auth.router,         prefix=PREFIX, tags=["Auth"])
app.include_router(companies.router,    prefix=PREFIX, tags=["Companies"])
app.include_router(transactions.router, prefix=PREFIX, tags=["Transactions"])
app.include_router(accounts.router,     prefix=PREFIX, tags=["Accounts"])
app.include_router(reports.router,      prefix=PREFIX, tags=["Reports"])
app.include_router(debts.router,        prefix=PREFIX, tags=["Debts"])
app.include_router(ai.router,           prefix=PREFIX, tags=["AI"])
app.include_router(tax.router,          prefix=PREFIX, tags=["Tax"])
app.include_router(documents.router,    prefix=PREFIX, tags=["Documents"])
app.include_router(customers.router,    prefix=PREFIX, tags=["Customers"])
app.include_router(suppliers.router,    prefix=PREFIX, tags=["Suppliers"])


# ─── Health Check ────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
    }
    @app.get("/", tags=["System"])
async def root():
    return {
        "status": "ok",
        "message": "Zentra API is running",
        "docs": "/docs",
        "health": "/health"
}
