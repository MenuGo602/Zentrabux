"""
Contract Service — standart shartnoma shabloni PDF generatsiyasi.

Bu servis DB'dagi biror tranzaksiyaga bog'liq emas — kompaniya
tomonlarning ma'lumotlari va shartnoma shartlarini to'g'ridan-to'g'ri
qabul qiladi (odatda yangi hamkorlik boshlanishida ishlatiladi).

DIQQAT: Bu YURIDIK MASLAHAT emas — umumiy andoza (shablon). Murakkab yoki
yuqori qiymatli bitimlar uchun professional yurist tekshiruvidan
o'tkazish tavsiya etiladi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

from app.services.document.pdf import CompanyInfo, DocumentContext, PDFBuilder, format_amount


class ContractType(StrEnum):
    SALE = "sale"            # Oldi-sotdi
    SERVICE = "service"      # Xizmat ko'rsatish
    LEASE = "lease"          # Ijara
    SUPPLY = "supply"        # Yetkazib berish


_CONTRACT_TITLES = {
    ContractType.SALE: "OLDI-SOTDI SHARTNOMASI",
    ContractType.SERVICE: "XIZMAT KO'RSATISH SHARTNOMASI",
    ContractType.LEASE: "IJARA SHARTNOMASI",
    ContractType.SUPPLY: "YETKAZIB BERISH SHARTNOMASI",
}

_SUBJECT_LABELS = {
    ContractType.SALE: "tovarni sotish",
    ContractType.SERVICE: "xizmat ko'rsatish",
    ContractType.LEASE: "mulkni ijaraga berish",
    ContractType.SUPPLY: "tovarni yetkazib berish",
}


@dataclass
class ContractParty:
    name: str
    inn: str | None = None
    address: str | None = None
    phone: str | None = None
    representative: str | None = None   # "direktor Aliyev A.A." kabi


@dataclass
class ContractTerms:
    contract_type: ContractType
    subject_description: str
    amount: Decimal
    currency: str = "UZS"
    payment_terms: str = "Shartnoma imzolangan kundan 5 ish kuni ichida to'liq to'lov"
    duration_description: str = "Shartnoma imzolangan kundan 1 yil muddatga tuziladi"
    additional_clauses: list[str] = field(default_factory=list)


class ContractService:
    def generate(
        self,
        company: ContractParty,
        counterparty: ContractParty,
        terms: ContractTerms,
        contract_number: str,
        issue_date: date | None = None,
    ) -> bytes:
        issue_date = issue_date or date.today()
        subject_label = _SUBJECT_LABELS[terms.contract_type]

        body = [
            f"1-BAND. SHARTNOMA PREDMETI. Ushbu shartnoma bo'yicha \"{company.name}\" "
            f"(bundan buyon — \"Ijrochi\") va \"{counterparty.name}\" (bundan buyon — \"Buyurtmachi\") "
            f"o'rtasida {subject_label} bo'yicha munosabatlar belgilanadi. "
            f"Predmet tavsifi: {terms.subject_description}",

            f"2-BAND. SHARTNOMA QIYMATI VA TO'LOV TARTIBI. Shartnoma umumiy qiymati "
            f"{format_amount(terms.amount, terms.currency)} ni tashkil etadi. To'lov tartibi: "
            f"{terms.payment_terms}",

            f"3-BAND. TOMONLARNING MAJBURIYATLARI. Ijrochi predmetni sifatli va o'z vaqtida "
            f"bajarishga, Buyurtmachi esa belgilangan tartibda to'lovni amalga oshirishga "
            f"majburdir.",

            "4-BAND. TOMONLARNING JAVOBGARLIGI. Shartnoma shartlarini bajarmagan tomon "
            "O'zbekiston Respublikasi qonunchiligiga muvofiq javobgar bo'ladi. Tomonlar "
            "o'zaro kelishuv yo'li bilan nizolarni hal qilishga harakat qiladilar; "
            "kelishuvga erishilmasa, nizo sudda ko'riladi.",

            f"5-BAND. SHARTNOMA MUDDATI. {terms.duration_description}",
        ]

        for i, clause in enumerate(terms.additional_clauses, start=6):
            body.append(f"{i}-BAND. {clause}")

        body.append(
            "YAKUNIY QOIDALAR. Ushbu shartnoma ikki nusxada, har bir tomon uchun bittadan, "
            "bir xil yuridik kuchga ega bo'lgan holda tuzildi."
        )

        context = DocumentContext(
            title=_CONTRACT_TITLES[terms.contract_type],
            document_number=contract_number,
            company=CompanyInfo(
                name=company.name, inn=company.inn, address=company.address, phone=company.phone,
            ),
            counterparty_name=counterparty.name,
            counterparty_inn=counterparty.inn,
            counterparty_address=counterparty.address,
            issue_date=str(issue_date),
            body_paragraphs=body,
            footer_note=(
                f"Zentra orqali generatsiya qilindi — {date.today()}. "
                "Bu shablon yuridik maslahat o'rnini bosmaydi."
            ),
        )

        return PDFBuilder(context).build()
