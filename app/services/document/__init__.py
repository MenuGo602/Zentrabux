"""
Document Service — biznes hujjatlarini (PDF/Excel) generatsiya qiladi.

Modullar:
    - ``invoice``   — hisob-faktura PDF
    - ``act``        — bajarilgan ishlar dalolatnomasi PDF
    - ``contract``   — shartnoma shabloni PDF
    - ``excel``      — hisobotlarni .xlsx eksport qilish
    - ``pdf``         — umumiy PDF qurish vositalari
    - ``qr``          — QR kod generatsiyasi

Barcha generatorlar faqat MAVJUD ma'lumotni (Transaction, Company,
TrialBalance va h.k.) formatlaydi — hech qanday hisob-kitob
(soliq, balans) o'zi bajarmaydi, bular Accounting/Tax Engine'dan keladi.
"""

from app.services.document.act import ActService
from app.services.document.contract import ContractService
from app.services.document.excel import ExcelExportService
from app.services.document.invoice import InvoiceService

__all__ = ["InvoiceService", "ActService", "ContractService", "ExcelExportService"]
