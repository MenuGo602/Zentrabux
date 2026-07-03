# Zentra Dashboard (Frontend)

React + Vite bilan qurilgan veb-dashboard. Backend bilan bir xil JWT
autentifikatsiya tizimidan foydalanadi (`app/api/v1/auth.py`), lekin
kirish uchun parol o'rniga **"Login with Telegram" widget** ishlatiladi —
chunki botdan ro'yxatdan o'tgan foydalanuvchilarda parol yo'q.

## Ishga tushirish

```bash
cd frontend
cp .env.example .env   # VITE_BOT_USERNAME'ni to'g'irlang
npm install
npm run dev
```

Yoki Docker orqali (API bilan birga):

```bash
docker compose --profile frontend up -d
```

## Telegram Login Widget sozlash

Widget ishlashi uchun @BotFather'da botingizning domenini ro'yxatdan
o'tkazish shart:

1. @BotFather → `/mybots` → botingizni tanlang → **Bot Settings** → **Domain**
2. Frontend ishlaydigan domenni kiriting (masalan `dashboard.zentra.uz`,
   lokal test uchun `localhost` ishlamaydi — ngrok yoki shunga o'xshash
   tunnel kerak bo'ladi)

## Arxitektura

```
src/
├── lib/apiClient.js       # Backend bilan HTTP (401'da avto-refresh)
├── lib/format.js          # Pul/sana formatlash
├── context/AuthContext.jsx # Token, foydalanuvchi, kompaniya holati
├── components/
│   ├── BalanceBeam.jsx     # "Aktivlar = Majburiyatlar" tarozi vizualizatsiyasi
│   ├── Layout.jsx          # Pastki navigatsiya + kompaniya almashtirgich
│   └── ...
└── pages/
    ├── Login.jsx
    ├── Dashboard.jsx
    ├── Transactions.jsx
    └── Debts.jsx
```

## Nega vanilla CSS, Tailwind emas?

Loyihada hali frontend build zanjiri (Tailwind/PostCSS konfiguratsiyasi)
yo'q edi — soddalik uchun CSS custom properties (`src/styles/tokens.css`)
asosidagi token tizimi ishlatildi. Kerak bo'lsa keyinroq Tailwind'ga
o'tish oson (tokenlar allaqachon markazlashtirilgan).

## Keyingi qadamlar (hali qilinmagan)

- Hisobotlar sahifasi (P&L, Balance Sheet — hozircha faqat Dashboard'da qisqacha)
- Kompaniya sozlamalari, xodimlarni boshqarish
- Soliq kalendari sahifasi
- Rus tiliga to'liq tarjima (hozircha faqat o'zbekcha)
