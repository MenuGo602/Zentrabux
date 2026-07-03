# ─── Base ───────────────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --upgrade pip && pip install -e ".[dev]"

# ─── Development ────────────────────────────────────────
FROM base AS development
COPY . .
EXPOSE 8000

# ─── Production ─────────────────────────────────────────
FROM base AS production
COPY . .

RUN addgroup --system zentra && adduser --system --group zentra
USER zentra

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
