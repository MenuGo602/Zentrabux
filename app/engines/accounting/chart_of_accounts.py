"""
Chart of Accounts — O'zbekiston standart schyotlar rejasi.

Moliya Vazirligi 23.10.2002 yildagi 103-sonli buyrug'i asosida
soddalashtirilgan, kichik biznes uchun moslashtirilgan ro'yxat.

Har bir yangi kompaniya ro'yxatdan o'tganda shu schyotlar
avtomatik yaratiladi (bootstrap_company_accounts orqali).
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.all_models import Account, AccountType


@dataclass(frozen=True)
class AccountDef:
    code: str
    name: str
    account_type: AccountType
    parent_code: str | None = None


# ─── Standart Schyotlar Ro'yxati ─────────────────────────────────────────────
STANDARD_ACCOUNTS: list[AccountDef] = [
    # ═══ 0-bo'lim: Uzoq muddatli aktivlar ═══
    AccountDef("0110", "Asosiy vositalar",                 AccountType.ASSET),
    AccountDef("0210", "Asosiy vositalar amortizatsiyasi",  AccountType.ASSET),
    AccountDef("0410", "Nomoddiy aktivlar",                 AccountType.ASSET),

    # ═══ 2-bo'lim: Tovar-moddiy zaxiralar ═══
    AccountDef("2010", "Sotilgan tovar tannarxi (COGS)",    AccountType.EXPENSE),
    AccountDef("2710", "Tovarlar",                          AccountType.ASSET),
    AccountDef("2910", "Tovar-moddiy boyliklar",            AccountType.ASSET),

    # ═══ 4-bo'lim: Debitorlik qarzlar ═══
    AccountDef("4010", "Xaridorlar bilan hisob-kitoblar",   AccountType.ASSET),
    AccountDef("4310", "Xodimlarga berilgan avans",         AccountType.ASSET),
    AccountDef("4810", "Boshqa debitorlik qarzlar",         AccountType.ASSET),

    # ═══ 5-bo'lim: Pul mablag'lari ═══
    AccountDef("5110", "Kassa (UZS)",                       AccountType.ASSET),
    AccountDef("5120", "Kassa (USD)",                       AccountType.ASSET),
    AccountDef("5210", "Hisob-kitob schyoti (UZS)",         AccountType.ASSET),
    AccountDef("5220", "Valyuta schyoti (USD)",             AccountType.ASSET),
    AccountDef("5510", "Elektron pul (Click/Payme)",        AccountType.ASSET),

    # ═══ 6-bo'lim: Majburiyatlar ═══
    AccountDef("6010", "Ta'minotchilar bilan hisob-kitob",  AccountType.LIABILITY),
    AccountDef("6410", "Byudjetga soliqlar bo'yicha qarz",  AccountType.LIABILITY),
    AccountDef("6420", "QQS bo'yicha qarz",                 AccountType.LIABILITY),
    AccountDef("6710", "Mehnat haqi bo'yicha qarz",         AccountType.LIABILITY),
    AccountDef("6810", "Ijtimoiy sug'urta bo'yicha qarz",   AccountType.LIABILITY),
    AccountDef("6910", "Boshqa kreditorlik qarzlar",        AccountType.LIABILITY),

    # ═══ 8-bo'lim: Kapital ═══
    AccountDef("8330", "Ustav kapitali",                    AccountType.EQUITY),
    AccountDef("8710", "Taqsimlanmagan foyda",               AccountType.EQUITY),
    AccountDef("8720", "Joriy yil foydasi/zarari",           AccountType.EQUITY),

    # ═══ 9-bo'lim: Daromadlar ═══
    AccountDef("9010", "Mahsulot/xizmat sotishdan daromad", AccountType.INCOME),
    AccountDef("9020", "Tovarlar sotishdan daromad",        AccountType.INCOME),
    AccountDef("9310", "Boshqa operatsion daromadlar",      AccountType.INCOME),
    AccountDef("9520", "Foiz daromadlari",                  AccountType.INCOME),

    # ═══ 7-bo'lim: Xarajatlar ═══
    AccountDef("7010", "Sotish xarajatlari",                AccountType.EXPENSE),
    AccountDef("7110", "Mehnat haqi xarajati",               AccountType.EXPENSE),
    AccountDef("7120", "Ijtimoiy sug'urta ajratmalari",      AccountType.EXPENSE),
    AccountDef("7210", "Amortizatsiya xarajatlari",          AccountType.EXPENSE),
    AccountDef("7310", "Ish safari xarajatlari",             AccountType.EXPENSE),
    AccountDef("7410", "Reklama xarajatlari",                AccountType.EXPENSE),
    AccountDef("7420", "Ijara xarajatlari",                  AccountType.EXPENSE),
    AccountDef("7430", "Kommunal xarajatlar",                AccountType.EXPENSE),
    AccountDef("7440", "Aloqa va internet xarajatlari",      AccountType.EXPENSE),
    AccountDef("7450", "Transport xarajatlari",              AccountType.EXPENSE),
    AccountDef("7460", "Ofis-kantselyariya xarajatlari",     AccountType.EXPENSE),
    AccountDef("7910", "Boshqa operatsion xarajatlar",       AccountType.EXPENSE),

    # ═══ 9-bo'lim: Boshqa daromad/xarajatlar ═══
    AccountDef("9430", "Boshqa xarajatlar",                  AccountType.EXPENSE),
    AccountDef("9610", "Foyda solig'i xarajati",             AccountType.EXPENSE),
]


# ─── Bootstrap funksiyasi ─────────────────────────────────────────────────────
async def bootstrap_company_accounts(company_id: str, db: AsyncSession) -> int:
    """
    Yangi kompaniya uchun standart schyotlar rejasini yaratadi.
    Idempotent: agar schyot mavjud bo'lsa, qayta yaratmaydi.

    Returns: yaratilgan schyotlar soni
    """
    # Mavjud kodlarni olish
    existing_result = await db.execute(
        select(Account.code).where(Account.company_id == company_id)
    )
    existing_codes = {row[0] for row in existing_result.all()}

    created = 0
    code_to_id: dict[str, str] = {}

    # 1-pass: barcha schyotlarni yaratish (parent_id'siz)
    for acc_def in STANDARD_ACCOUNTS:
        if acc_def.code in existing_codes:
            continue

        account = Account(
            company_id=company_id,
            code=acc_def.code,
            name=acc_def.name,
            account_type=acc_def.account_type,
            is_system=True,
            is_active=True,
        )
        db.add(account)
        await db.flush()
        code_to_id[acc_def.code] = str(account.id)
        created += 1

    # 2-pass: parent_id larni bog'lash
    for acc_def in STANDARD_ACCOUNTS:
        if acc_def.parent_code and acc_def.code in code_to_id:
            result = await db.execute(
                select(Account).where(Account.id == code_to_id[acc_def.code])
            )
            account = result.scalar_one()
            account.parent_id = code_to_id.get(acc_def.parent_code)

    await db.flush()
    return created
