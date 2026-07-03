from aiogram.fsm.state import State, StatesGroup


class CompanyOnboarding(StatesGroup):
    waiting_name = State()


class VATCalculator(StatesGroup):
    waiting_amount = State()


class DebtCreation(StatesGroup):
    waiting_type = State()
    waiting_counterparty = State()
    waiting_new_counterparty_name = State()
    waiting_description = State()
    waiting_amount = State()
