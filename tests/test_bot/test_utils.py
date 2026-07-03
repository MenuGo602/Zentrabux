from datetime import date, timedelta

from app.bot.utils import format_money, period_bounds


class TestPeriodBounds:
    def test_today_returns_same_start_and_end(self):
        start, end = period_bounds("today")
        assert start == end == date.today()

    def test_week_starts_on_monday(self):
        start, end = period_bounds("week")
        assert start.weekday() == 0  # Dushanba
        assert end == date.today()

    def test_month_starts_on_first_day(self):
        start, end = period_bounds("month")
        assert start.day == 1
        assert start.month == date.today().month
        assert end == date.today()

    def test_last_month_is_fully_before_current_month(self):
        start, end = period_bounds("last_month")
        assert start.day == 1
        assert end < date.today().replace(day=1)
        assert (end - start).days >= 27  # Har qanday oy kamida 28 kun

    def test_unknown_key_defaults_to_month(self):
        assert period_bounds("noise") == period_bounds("month")


class TestFormatMoney:
    def test_formats_uzs_with_spaces_and_suffix(self):
        assert format_money(1_500_000) == "1 500 000 so'm"

    def test_formats_other_currency_with_code(self):
        assert format_money(100, "USD") == "100 USD"

    def test_rounds_to_whole_units(self):
        assert format_money(999.4) == "999 so'm"
