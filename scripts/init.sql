-- Zentra — PostgreSQL boshlang'ich sozlamalar

-- UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- Matn qidirish uchun

-- ─── Foydali funksiyalar ─────────────────────────────────────────────────────

-- Remaining amount avtomatik hisoblash
CREATE OR REPLACE FUNCTION update_debt_remaining()
RETURNS TRIGGER AS $$
BEGIN
    NEW.remaining_amount := NEW.original_amount - NEW.paid_amount;

    IF NEW.remaining_amount <= 0 THEN
        NEW.status := 'paid';
    ELSIF NEW.paid_amount > 0 THEN
        NEW.status := 'partially_paid';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger: qarz to'langanda remaining yangilansin
CREATE TRIGGER debt_remaining_trigger
    BEFORE INSERT OR UPDATE OF paid_amount ON debts
    FOR EACH ROW EXECUTE FUNCTION update_debt_remaining();

-- updated_at avtomatik yangilash
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
