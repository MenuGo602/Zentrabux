from decimal import Decimal

from app.services.document.contract import (
    ContractParty,
    ContractService,
    ContractTerms,
    ContractType,
)


class TestContractService:
    def test_generates_valid_sale_contract_pdf(self):
        company = ContractParty(name="Zentra Test MCHJ", inn="123456789", address="Toshkent")
        counterparty = ContractParty(name="Mijoz Supplier", inn="987654321")
        terms = ContractTerms(
            contract_type=ContractType.SALE,
            subject_description="1000 dona g'isht yetkazib berish",
            amount=Decimal("15000000"),
        )

        service = ContractService()
        pdf_bytes = service.generate(company, counterparty, terms, contract_number="C-2026-001")

        assert pdf_bytes.startswith(b"%PDF")

    def test_generates_valid_service_contract_with_additional_clauses(self):
        company = ContractParty(name="Zentra Test MCHJ")
        counterparty = ContractParty(name="Buyurtmachi LLC")
        terms = ContractTerms(
            contract_type=ContractType.SERVICE,
            subject_description="Buxgalteriya xizmati",
            amount=Decimal("2000000"),
            additional_clauses=["Maxfiylik shartlari saqlanadi.", "Force-major holatlar."],
        )

        service = ContractService()
        pdf_bytes = service.generate(company, counterparty, terms, contract_number="C-2026-002")

        assert pdf_bytes.startswith(b"%PDF")

    def test_all_contract_types_produce_distinct_titles(self):
        from app.services.document.contract import _CONTRACT_TITLES

        titles = set(_CONTRACT_TITLES.values())
        assert len(titles) == len(ContractType)
