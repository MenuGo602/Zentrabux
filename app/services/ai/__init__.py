"""
AI Service — Zentra'ning "miyasi".

Mas'uliyat doirasi (qat'iy chegaralangan):
    ✅ Foydalanuvchi xabaridan niyatni (intent) aniqlash
    ✅ Tranzaksiya ma'lumotlarini matn/rasmdan ajratib olish (extraction/OCR)
    ✅ Foydalanuvchi xatti-harakatlarini "eslab qolish" (AI Memory)
    ✅ Tabiiy tilda javob shakllantirish

    ❌ AI hech qachon jurnal yozuvini o'zi yaratmaydi — buni faqat
       AccountingEngine bajaradi.
    ❌ AI hech qachon soliq summasini o'zi hisoblamaydi — buni faqat
       TaxEngine bajaradi.

AI faqat "niyatni aniqlaydi", qolgan hamma narsa deterministik Engine'lar
orqali bajariladi. Shu tufayli AI xato qilsa ham, buxgalteriya
ma'lumotlari hech qachon buzilmaydi.
"""

from app.services.ai.orchestrator import AIOrchestrator

__all__ = ["AIOrchestrator"]
