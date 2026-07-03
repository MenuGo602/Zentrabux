# Zentra — AI-powered Accounting Platform

> O'rta Osiyo uchun sun'iy intellekt asosidagi buxgalteriya platformasi

## Arxitektura

```
Telegram Bot │ Web Dashboard │ Mobile App
                    │
              FastAPI (API-first)
                    │
    ┌───────────────┼───────────────┐
    │               │               │
Accounting      AI Service      Tax Engine
  Engine      (intent only)    (UZ/KZ/KG)
    │               │               │
    └───────────────┼───────────────┘
                    │
              PostgreSQL + Redis
```

**Asosiy prinsip:** AI faqat niyatni aniqlaydi. Barcha hisob-kitoblar Accounting Engine bajaradi.

## Tezkor Ishga Tushirish

```bash
# 1. Repo klonlash
git clone https://github.com/yourorg/zentra.git
cd zentra

# 2. Environment sozlash
cp .env.example .env
# .env faylni tahrirlang

# 3. Ishga tushirish
docker compose up -d

# 4. Migration
docker compose exec api alembic upgrade head

# API tayyor: http://localhost:8000/docs
```

## Bosqichlar

| Bosqich | Modul | Holat |
|---------|-------|-------|
| 1 | Database Migrations | ✅ |
| 1 | FastAPI Skeleton | ✅ |
| 2 | Accounting Engine | ✅ |
| 3 | Tax Engine (UZ) | ✅ |
| 4 | AI Services | ✅ |
| 5 | Telegram Bot | ✅ (MVP) |
| 5 | Document Service | ✅ |
| 6 | Web Dashboard | ✅ (MVP) |

## Fayl Strukturasi

```
zentra/
├── app/
│   ├── main.py              # FastAPI app
│   ├── bot/                 # Telegram Bot (aiogram 3.x, backend API'ga thin klient)
│   ├── core/                # Config, DB, Security
│   ├── models/              # SQLAlchemy modellari
│   ├── api/v1/              # REST Endpointlar
│   ├── engines/
│   │   ├── accounting/      # ← YURAK: Double-entry engine
│   │   ├── tax/             # Soliq modullari (UZ/KZ/KG)
│   │   └── report/          # P&L, Balance, Cashflow
│   ├── services/
│   │   ├── ai/              # Intent, Extract, Memory, OCR
│   │   ├── document/        # Invoice/Akt/Shartnoma PDF, Excel export, QR
│   │   └── notification/    # Telegram, Email, Push, SMS
│   ├── events/              # Event Bus
│   └── tasks/               # Celery background tasks
├── migrations/              # Alembic
├── frontend/                # React + Vite veb-dashboard
├── tests/
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## Telegram Botni Ishga Tushirish

```bash
# .env faylga BOT_TOKEN qo'shing (@BotFather'dan olinadi)
# Docker orqali (API bilan birga):
docker compose --profile bot up -d

# Yoki lokal (API allaqachon ishlab turgan bo'lishi kerak):
export API_BASE_URL=http://localhost:8000
python -m app.bot.main
```

Bot birinchi `/start` bosilganda foydalanuvchini avtomatik ro'yxatdan
o'tkazadi (`POST /auth/telegram` — parolsiz), so'ng kompaniya
tanlash/yaratishni so'raydi. Undan keyin oddiy o'zbek tilida yozilgan
xabarlar (`"500 mingga tovar sotdim"`) to'g'ridan-to'g'ri AI
Orchestrator'ga (`POST /ai/{company_id}/chat`) yuboriladi.

## Veb Dashboardni Ishga Tushirish

```bash
cd frontend
cp .env.example .env   # VITE_BOT_USERNAME'ni to'g'irlang
npm install
npm run dev
```

Yoki: `docker compose --profile frontend up -d`

Kirish — "Login with Telegram" widget orqali (`POST /auth/telegram-widget`).
Batafsil: [`frontend/README.md`](frontend/README.md).


## Rollar

| Funksiya | Owner | Accountant | Employee |
|----------|-------|------------|----------|
| Tranzaksiya qo'shish | ✅ | ✅ | ✅ |
| Tasdiqlash | ✅ | ✅ | ❌ |
| Hisobotlar | ✅ | ✅ | ❌ |
| Xodim qo'shish | ✅ | ❌ | ❌ |
| AI suhbat | ✅ | ✅ | ✅ |

## Texnologiyalar

- **Backend:** FastAPI + SQLAlchemy (async) + PostgreSQL
- **Cache/Queue:** Redis + Celery
- **AI:** OpenAI GPT-4o-mini (almashtirish mumkin)
- **Bot:** aiogram 3.x
- **Auth:** JWT (access + refresh tokens)
- **CI/CD:** GitHub Actions + Docker
