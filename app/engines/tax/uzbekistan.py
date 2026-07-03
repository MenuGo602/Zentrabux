"""
Uzbekistan Tax Engine — 2026-yil stavkalari.

Manba: O'zbekiston Respublikasi Soliq Kodeksi,
2026-2028 yillarga mo'ljallangan Byudjetnoma (IFM e'loni, 2025-yil noyabr-dekabr).

Asosiy stavkalar (2026, o'zgarishsiz qoldi):
    QQS (umumiy)              — 12%
    QQS (soddalashtirilgan)   — 6%  (2026-yil 1-iyundan, umumiy ovqatlanish/savdo/xizmat)
    Foyda solig'i             — 15%
    Aylanmadan olinadigan     — 4%  (YATT uchun 1 mlrd so'mgacha — 1%)
    Ijtimoiy soliq            — 12% (budjet tashkilotlari — 25%)
    Mol-mulk solig'i (YUR)    — 1.5%
    Yer solig'i (q/x)         — 0.95%

Muhim chegaralar:
    1 mlrd so'm   — YATT uchun aylanma soliq chegarasi (undan keyin QQS+foyda solig'i majburiy)
    4.944 mlrd    — 2026-yil 1-iyundan umumiy rejimga o'tish chegarasi (12 000 BHM)
    20 mlrd so'm  — Foyda solig'i bo'yicha oylik avans to'lash chegarasi (2026: 10→20 mlrd)

DIQQAT: Bu modul ma'lumot uchun, professional soliq maslahatidan
foydalanish tavsiya etiladi. Qonunchilik tez-tez o'zgaradi —
har chorakda QQS/IFM saytlarini tekshirib turish kerak.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.engines.tax.base import BaseTaxEngine, TaxCalendarEntry, TaxResult


@dataclass(frozen=True)
class UZTaxRates:
    """2026-yil uchun rasmiy stavkalar"""
    VAT_STANDARD: Decimal = Decimal("12.00")
    VAT_SIMPLIFIED: Decimal = Decimal("6.00")          # Umumiy ovqatlanish/savdo/xizmat, 2026.06.01+
    VAT_AGRICULTURE: Decimal = Decimal("0.00")          # Qishloq xo'jaligi ishlab chiqaruvchilari

    PROFIT_TAX: Decimal = Decimal("15.00")
    PROFIT_TAX_ECOMMERCE: Decimal = Decimal("15.00")    # Amalda 10%, 2026dan 15%ga ko'tariladi

    TURNOVER_TAX_STANDARD: Decimal = Decimal("4.00")
    TURNOVER_TAX_INDIVIDUAL: Decimal = Decimal("1.00")  # YATT/o'zini band — 1 mlrd so'mgacha
    TURNOVER_TAX_ECOMMERCE: Decimal = Decimal("4.00")    # Amalda 3%, 2026dan 4%ga ko'tariladi

    SOCIAL_TAX_STANDARD: Decimal = Decimal("12.00")
    SOCIAL_TAX_BUDGET_ORG: Decimal = Decimal("25.00")

    PROPERTY_TAX_LEGAL: Decimal = Decimal("1.50")
    LAND_TAX_AGRICULTURE: Decimal = Decimal("0.95")

    # Chegaralar (so'mda)
    TURNOVER_TAX_THRESHOLD: Decimal = Decimal("1_010_000_000")       # 1.01 mlrd — bu chegaradan keyin majburiy QQS+foyda solig'i
    GENERAL_REGIME_THRESHOLD_2026: Decimal = Decimal("4_944_000_000")  # 2026.06.01dan, 12000 BHM
    MONTHLY_ADVANCE_THRESHOLD: Decimal = Decimal("20_000_000_000")    # Foyda solig'i oylik avans chegarasi


RATES = UZTaxRates()


class UzbekistanTaxEngine(BaseTaxEngine):
    country_code = "UZB"
    country_name = "O'zbekiston"

    # ─── QQS ──────────────────────────────────────────────────────────────────
    async def calculate_vat(
        self,
        taxable_amount: Decimal,
        company_id: str,
        is_vat_payer: bool = True,
        is_simplified: bool = False,
        is_agriculture: bool = False,
        **kwargs,
    ) -> TaxResult | None:
        """
        QQS hisoblash.

        is_vat_payer=False bo'lsa → None (QQS to'lovchisi emas)
        is_simplified=True       → 6% (umumiy ovqatlanish/savdo/xizmat, ixtiyoriy)
        is_agriculture=True      → 0% (q/x ishlab chiqaruvchilari, o'z mahsuloti)
        """
        if not is_vat_payer:
            return None

        if is_agriculture:
            rate = RATES.VAT_AGRICULTURE
            note = "Qishloq xo'jaligi ishlab chiqaruvchilari uchun QQS 0%"
        elif is_simplified:
            rate = RATES.VAT_SIMPLIFIED
            note = "Soddalashtirilgan QQS (6%) — kiruvchi QQS hisobga olinmaydi, foyda solig'i 0%"
        else:
            rate = RATES.VAT_STANDARD
            note = "Standart QQS stavkasi"

        tax_amount = (taxable_amount * rate / Decimal("100")).quantize(Decimal("0.01"))

        return TaxResult(
            tax_type="vat",
            tax_name="Qo'shilgan qiymat solig'i (QQS)",
            taxable_amount=taxable_amount,
            rate=rate,
            tax_amount=tax_amount,
            notes=note,
        )

    # ─── Foyda solig'i ───────────────────────────────────────────────────────
    async def calculate_profit_tax(
        self,
        net_profit: Decimal,
        company_id: str,
        is_simplified_vat: bool = False,
        is_first_year_after_transition: bool = False,
        **kwargs,
    ) -> TaxResult | None:
        """
        Foyda solig'i. Zarar bo'lsa (net_profit <= 0) → soliq yo'q.

        is_simplified_vat=True → 0% (soddalashtirilgan QQS rejimida foyda solig'i yo'q)
        is_first_year_after_transition=True → aylanma solig'idan QQS+foyda solig'iga
            o'tgan kompaniyalar uchun birinchi yil foyda solig'idan ozod
        """
        if net_profit <= 0:
            return TaxResult(
                tax_type="profit_tax",
                tax_name="Foyda solig'i",
                taxable_amount=Decimal("0"),
                rate=RATES.PROFIT_TAX,
                tax_amount=Decimal("0"),
                notes="Zarar yoki nol foyda — soliq hisoblanmadi",
            )

        if is_simplified_vat:
            return TaxResult(
                tax_type="profit_tax",
                tax_name="Foyda solig'i",
                taxable_amount=net_profit,
                rate=Decimal("0"),
                tax_amount=Decimal("0"),
                notes="Soddalashtirilgan QQS rejimida foyda solig'i 0%",
            )

        if is_first_year_after_transition:
            return TaxResult(
                tax_type="profit_tax",
                tax_name="Foyda solig'i",
                taxable_amount=net_profit,
                rate=Decimal("0"),
                tax_amount=Decimal("0"),
                notes="Aylanma solig'idan o'tgan birinchi yil — foyda solig'idan ozod",
            )

        rate = RATES.PROFIT_TAX
        tax_amount = (net_profit * rate / Decimal("100")).quantize(Decimal("0.01"))

        return TaxResult(
            tax_type="profit_tax",
            tax_name="Foyda solig'i",
            taxable_amount=net_profit,
            rate=rate,
            tax_amount=tax_amount,
            notes="Bazaviy stavka 15%",
        )

    # ─── Aylanmadan olinadigan soliq ─────────────────────────────────────────
    async def calculate_turnover_tax(
        self,
        revenue: Decimal,
        company_id: str,
        is_individual_entrepreneur: bool = False,
        **kwargs,
    ) -> TaxResult | None:
        """
        Aylanma solig'i — soddalashtirilgan rejim (1.01 mlrd so'mgacha aylanma).

        Agar aylanma chegaradan oshsa → None qaytaradi
        (bu holda QQS + foyda solig'i ishlatilishi kerak).
        """
        if revenue >= RATES.TURNOVER_TAX_THRESHOLD:
            return None  # Umumiy rejimga o'tish kerak

        if is_individual_entrepreneur and revenue <= Decimal("1_000_000_000"):
            rate = RATES.TURNOVER_TAX_INDIVIDUAL
            note = "YATT/o'zini band qilgan shaxs uchun imtiyozli stavka (1 mlrd so'mgacha)"
        else:
            rate = RATES.TURNOVER_TAX_STANDARD
            note = "Standart aylanma solig'i stavkasi"

        tax_amount = (revenue * rate / Decimal("100")).quantize(Decimal("0.01"))

        return TaxResult(
            tax_type="turnover_tax",
            tax_name="Aylanmadan olinadigan soliq",
            taxable_amount=revenue,
            rate=rate,
            tax_amount=tax_amount,
            notes=note,
        )

    # ─── Ijtimoiy soliq ──────────────────────────────────────────────────────
    async def calculate_social_tax(
        self,
        salary_fund: Decimal,
        company_id: str,
        is_budget_organization: bool = False,
        **kwargs,
    ) -> TaxResult:
        """Ish haqi fondidan ijtimoiy soliq — ish beruvchi to'laydi"""
        rate = RATES.SOCIAL_TAX_BUDGET_ORG if is_budget_organization else RATES.SOCIAL_TAX_STANDARD
        tax_amount = (salary_fund * rate / Decimal("100")).quantize(Decimal("0.01"))

        return TaxResult(
            tax_type="social_tax",
            tax_name="Ijtimoiy soliq",
            taxable_amount=salary_fund,
            rate=rate,
            tax_amount=tax_amount,
            notes="Budjet tashkiloti uchun 25%" if is_budget_organization else "Standart stavka 12%",
        )

    # ─── Soliq rejimini aniqlash ──────────────────────────────────────────────
    def determine_regime(self, annual_revenue: Decimal) -> str:
        """
        Yillik aylanmaga ko'ra qaysi soliq rejimi tegishli ekanini aniqlaydi.

        Natija:
            "turnover_tax" — soddalashtirilgan (aylanma solig'i)
            "general"      — umumiy rejim (QQS + foyda solig'i)
        """
        if annual_revenue < RATES.TURNOVER_TAX_THRESHOLD:
            return "turnover_tax"
        return "general"

    def check_regime_transition_warning(self, current_revenue: Decimal) -> str | None:
        """
        Chegaraga yaqinlashganda ogohlantirish (90% dan oshsa).
        AI Memory/Notification orqali foydalanuvchiga yuboriladi.
        """
        threshold = RATES.TURNOVER_TAX_THRESHOLD
        warning_zone = threshold * Decimal("0.9")

        if current_revenue >= threshold:
            return (
                f"⚠️ Yillik aylanmangiz {current_revenue:,.0f} so'mga yetdi — "
                f"1.01 mlrd chegarasidan oshdi. Keyingi oydan QQS va foyda solig'i "
                f"to'lovchisi sifatida ro'yxatdan o'tishingiz SHART."
            )
        elif current_revenue >= warning_zone:
            remaining = threshold - current_revenue
            return (
                f"📊 Yillik aylanmangiz {current_revenue:,.0f} so'm — chegaragacha "
                f"{remaining:,.0f} so'm qoldi. QQS rejimiga o'tishga tayyorgarlik "
                f"ko'rishni tavsiya qilamiz (6-12 oy oldin boshlash maqsadga muvofiq)."
            )
        return None

    # ─── Soliq Taqvimi ───────────────────────────────────────────────────────
    def get_tax_calendar(self, year: int) -> list[TaxCalendarEntry]:
        """
        2026-yil uchun asosiy soliq taqvimi.
        Har chorak/oy uchun deklaratsiya va to'lov muddatlari.
        """
        entries: list[TaxCalendarEntry] = []

        # QQS — har oy, keyingi oyning 20-sigacha
        for month in range(1, 13):
            next_month = month + 1 if month < 12 else 1
            next_year = year if month < 12 else year + 1
            entries.append(
                TaxCalendarEntry(
                    tax_type="vat",
                    tax_name="QQS deklaratsiyasi va to'lovi",
                    deadline=date(next_year, next_month, 20),
                    period_description=f"{year}-yil {month}-oy uchun",
                    is_filing=True,
                )
            )

        # Foyda solig'i — choraklik avans, yillik yakuniy hisobot
        quarter_deadlines = [
            (date(year, 4, 25), f"{year}-yil 1-chorak"),
            (date(year, 7, 25), f"{year}-yil 2-chorak"),
            (date(year, 10, 25), f"{year}-yil 3-chorak"),
            (date(year + 1, 1, 25), f"{year}-yil 4-chorak (yakuniy)"),
        ]
        for deadline, period in quarter_deadlines:
            entries.append(
                TaxCalendarEntry(
                    tax_type="profit_tax",
                    tax_name="Foyda solig'i deklaratsiyasi",
                    deadline=deadline,
                    period_description=period,
                    is_filing=True,
                )
            )

        # Aylanma solig'i — choraklik
        turnover_deadlines = [
            (date(year, 4, 25), f"{year}-yil 1-chorak"),
            (date(year, 7, 25), f"{year}-yil 2-chorak"),
            (date(year, 10, 25), f"{year}-yil 3-chorak"),
            (date(year + 1, 1, 25), f"{year}-yil 4-chorak"),
        ]
        for deadline, period in turnover_deadlines:
            entries.append(
                TaxCalendarEntry(
                    tax_type="turnover_tax",
                    tax_name="Aylanma solig'i deklaratsiyasi",
                    deadline=deadline,
                    period_description=period,
                    is_filing=True,
                )
            )

        # Ijtimoiy soliq — har oy, keyingi oyning 15-sigacha
        for month in range(1, 13):
            next_month = month + 1 if month < 12 else 1
            next_year = year if month < 12 else year + 1
            entries.append(
                TaxCalendarEntry(
                    tax_type="social_tax",
                    tax_name="Ijtimoiy soliq to'lovi",
                    deadline=date(next_year, next_month, 15),
                    period_description=f"{year}-yil {month}-oy uchun",
                    is_filing=False,
                )
            )

        # Mol-mulk solig'i — choraklik
        for deadline, period in quarter_deadlines:
            entries.append(
                TaxCalendarEntry(
                    tax_type="property_tax",
                    tax_name="Mol-mulk solig'i",
                    deadline=deadline,
                    period_description=period,
                    is_filing=True,
                )
            )

        return sorted(entries, key=lambda e: e.deadline)

    def get_upcoming_deadlines(self, from_date: date, days_ahead: int = 30) -> list[TaxCalendarEntry]:
        """Yaqin orada keladigan muddatlarni qaytaradi — bildirishnoma uchun"""
        from datetime import timedelta

        all_entries = self.get_tax_calendar(from_date.year)
        if from_date.month == 12:
            all_entries += self.get_tax_calendar(from_date.year + 1)

        cutoff = from_date + timedelta(days=days_ahead)
        return [e for e in all_entries if from_date <= e.deadline <= cutoff]
