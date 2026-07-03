"""
O'zbekiston Tax Engine testlari.

2026-yil rasmiy stavkalariga mos kelishini tekshiradi:
QQS 12% (yoki 6% soddalashtirilgan), Foyda solig'i 15%,
Aylanma solig'i 4% (YATT uchun 1%), Ijtimoiy soliq 12%.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.engines.tax.uzbekistan import RATES, UzbekistanTaxEngine


@pytest.fixture
def engine() -> UzbekistanTaxEngine:
    return UzbekistanTaxEngine()


class TestVAT:
    async def test_standard_vat_rate_is_12_percent(self, engine: UzbekistanTaxEngine):
        result = await engine.calculate_vat(
            taxable_amount=Decimal("1_000_000"),
            company_id="test",
            is_vat_payer=True,
        )
        assert result is not None
        assert result.rate == Decimal("12.00")
        assert result.tax_amount == Decimal("120000.00")

    async def test_simplified_vat_rate_is_6_percent(self, engine: UzbekistanTaxEngine):
        result = await engine.calculate_vat(
            taxable_amount=Decimal("1_000_000"),
            company_id="test",
            is_vat_payer=True,
            is_simplified=True,
        )
        assert result is not None
        assert result.rate == Decimal("6.00")
        assert result.tax_amount == Decimal("60000.00")

    async def test_non_vat_payer_returns_none(self, engine: UzbekistanTaxEngine):
        result = await engine.calculate_vat(
            taxable_amount=Decimal("1_000_000"),
            company_id="test",
            is_vat_payer=False,
        )
        assert result is None

    async def test_agriculture_vat_is_zero(self, engine: UzbekistanTaxEngine):
        result = await engine.calculate_vat(
            taxable_amount=Decimal("5_000_000"),
            company_id="test",
            is_vat_payer=True,
            is_agriculture=True,
        )
        assert result.rate == Decimal("0.00")
        assert result.tax_amount == Decimal("0.00")


class TestProfitTax:
    async def test_standard_rate_is_15_percent(self, engine: UzbekistanTaxEngine):
        result = await engine.calculate_profit_tax(
            net_profit=Decimal("10_000_000"),
            company_id="test",
        )
        assert result.rate == Decimal("15.00")
        assert result.tax_amount == Decimal("1500000.00")

    async def test_loss_means_zero_tax(self, engine: UzbekistanTaxEngine):
        result = await engine.calculate_profit_tax(
            net_profit=Decimal("-500_000"),
            company_id="test",
        )
        assert result.tax_amount == Decimal("0")

    async def test_simplified_vat_means_zero_profit_tax(self, engine: UzbekistanTaxEngine):
        """Soddalashtirilgan QQS rejimida foyda solig'i 0% bo'lishi kerak"""
        result = await engine.calculate_profit_tax(
            net_profit=Decimal("10_000_000"),
            company_id="test",
            is_simplified_vat=True,
        )
        assert result.rate == Decimal("0")
        assert result.tax_amount == Decimal("0")

    async def test_first_year_transition_exempt(self, engine: UzbekistanTaxEngine):
        """Aylanma solig'idan o'tgan birinchi yil — foyda solig'idan ozod"""
        result = await engine.calculate_profit_tax(
            net_profit=Decimal("50_000_000"),
            company_id="test",
            is_first_year_after_transition=True,
        )
        assert result.tax_amount == Decimal("0")


class TestTurnoverTax:
    async def test_standard_rate_is_4_percent(self, engine: UzbekistanTaxEngine):
        result = await engine.calculate_turnover_tax(
            revenue=Decimal("500_000_000"),
            company_id="test",
        )
        assert result is not None
        assert result.rate == Decimal("4.00")
        assert result.tax_amount == Decimal("20000000.00")

    async def test_individual_entrepreneur_rate_is_1_percent(self, engine: UzbekistanTaxEngine):
        result = await engine.calculate_turnover_tax(
            revenue=Decimal("500_000_000"),
            company_id="test",
            is_individual_entrepreneur=True,
        )
        assert result.rate == Decimal("1.00")
        assert result.tax_amount == Decimal("5000000.00")

    async def test_above_threshold_returns_none(self, engine: UzbekistanTaxEngine):
        """1.01 mlrd so'mdan oshsa — umumiy rejimga o'tish kerak, None qaytadi"""
        result = await engine.calculate_turnover_tax(
            revenue=Decimal("1_500_000_000"),
            company_id="test",
        )
        assert result is None


class TestSocialTax:
    async def test_standard_rate_is_12_percent(self, engine: UzbekistanTaxEngine):
        result = await engine.calculate_social_tax(
            salary_fund=Decimal("10_000_000"),
            company_id="test",
        )
        assert result.rate == Decimal("12.00")
        assert result.tax_amount == Decimal("1200000.00")

    async def test_budget_org_rate_is_25_percent(self, engine: UzbekistanTaxEngine):
        result = await engine.calculate_social_tax(
            salary_fund=Decimal("10_000_000"),
            company_id="test",
            is_budget_organization=True,
        )
        assert result.rate == Decimal("25.00")
        assert result.tax_amount == Decimal("2500000.00")


class TestRegimeDetermination:
    def test_below_threshold_is_turnover_regime(self, engine: UzbekistanTaxEngine):
        regime = engine.determine_regime(Decimal("500_000_000"))
        assert regime == "turnover_tax"

    def test_above_threshold_is_general_regime(self, engine: UzbekistanTaxEngine):
        regime = engine.determine_regime(Decimal("2_000_000_000"))
        assert regime == "general"

    def test_warning_triggers_near_threshold(self, engine: UzbekistanTaxEngine):
        # 95% of threshold
        near_threshold = RATES.TURNOVER_TAX_THRESHOLD * Decimal("0.95")
        warning = engine.check_regime_transition_warning(near_threshold)
        assert warning is not None
        assert "chegaragacha" in warning

    def test_no_warning_when_far_from_threshold(self, engine: UzbekistanTaxEngine):
        warning = engine.check_regime_transition_warning(Decimal("100_000_000"))
        assert warning is None

    def test_mandatory_warning_above_threshold(self, engine: UzbekistanTaxEngine):
        warning = engine.check_regime_transition_warning(Decimal("1_100_000_000"))
        assert warning is not None
        assert "SHART" in warning


class TestTaxCalendar:
    def test_calendar_has_monthly_vat_entries(self, engine: UzbekistanTaxEngine):
        entries = engine.get_tax_calendar(2026)
        vat_entries = [e for e in entries if e.tax_type == "vat"]
        assert len(vat_entries) == 12   # Har oy

    def test_calendar_entries_sorted_by_date(self, engine: UzbekistanTaxEngine):
        entries = engine.get_tax_calendar(2026)
        dates = [e.deadline for e in entries]
        assert dates == sorted(dates)

    def test_upcoming_deadlines_within_range(self, engine: UzbekistanTaxEngine):
        from_date = date(2026, 1, 10)
        upcoming = engine.get_upcoming_deadlines(from_date, days_ahead=15)
        for entry in upcoming:
            assert from_date <= entry.deadline <= date(2026, 1, 25)
