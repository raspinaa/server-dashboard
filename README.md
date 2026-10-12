# InfraHub | اینفراهاب

پورتال فارسی و راست‌به‌چپ برای موجودی ماشین‌ها و پروژه‌ها با Django، React و MySQL. گردش کار: تعریف پروژه ← XLSX ← اعتبارسنجی و تصمیم ← ورود تراکنشی ← ویرایش و فعالیت ← خروجی.

**این تحویل فقط سورس است.** سورس برای نگهداری در GitHub آماده شده است؛ هیچ استقرار عملیاتی، انتشار release یا اتصال به زیرساخت انجام نشده است. برنامه به vCenter، ESXi و ماشین‌ها وصل نمی‌شود. مسیر vCenter فقط شرح پروژه است؛ نمودارها منابع تخصیص‌یافته در رکوردها هستند.

## اجرا در توسعه

نیازمندی: Python 3.12، Node 24، Docker/Compose (یا MySQL 8.4 مجزا). دستورات زیر فقط برای محیط توسعه هستند:

```bash
python3.12 -m venv .venv
# روی Linux برای mysqlclient به compiler، pkg-config و MySQL/MariaDB development headers نیاز است.
.venv/bin/pip install --require-hashes -r backend/requirements.lock
docker compose -f deploy/compose.dev.yml up -d --wait
.venv/bin/python scripts/dev.py migrate
.venv/bin/python scripts/dev.py seed
.venv/bin/python scripts/dev.py server
# در ترمینال جداگانه:
cd frontend
npm ci
npm run dev
```

صفحه توسعه روی پورت 5173 است؛ Vite درخواست‌های API را به پورت 8000 هدایت می‌کند. حساب نمونه صرفاً محلی: `demo-admin` و `Isolated-Demo-Password-2026!`. دستور seed خارج از DEBUG اجرا نمی‌شود. `.env.dev` کلیدهای تصادفی محلی تولید می‌کند و در بسته انتشار قرار نمی‌گیرد. داده‌های seed هیچ رمز ماشین ندارند.

برای MySQL توسعه موجود از `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD` در محیط استفاده کنید. تست‌ها پایگاه داده جداگانه `test_infrahub` می‌سازند؛ کاربر آزمون به مجوز CREATE/DROP همان پایگاه نیاز دارد. آزمون روی دیتابیس عملیاتی اجرا نشود.

## بررسی‌ها

```bash
.venv/bin/python scripts/dev.py check
MYSQL_USER=root MYSQL_PASSWORD=local-test-root-only MYSQL_PORT=3306 .venv/bin/python scripts/dev.py test
cd frontend
npm run typecheck
npm test
npm run build
# پس از migrate، seed و راه‌اندازی backend:
npx playwright install chromium
npm run test:e2e
```

[گزارش بررسی‌ها](docs/verification.md) نتیجه واقعی اجراها و موارد تأییدنشده را ثبت می‌کند.

## ساختار و راهنما

- `backend/`: مدل‌های صریح، مهاجرت MySQL، API و آزمون‌های دسترسی/تراکنش.
- `frontend/`: رابط فارسی، موجودی، نمودار، ویرایش، تاریخچه، مراکز ورود/خروج و دسترسی.
- `deploy/`: Dockerfiles، Compose، InnoDB/utf8mb4، Caddy و سرویس اختیاری helper.
- `scripts/`: نصب (پیش‌فرض فقط نمایش برنامه)، پشتیبان، بازیابی، ارتقا، امضای بسته و دانلود فقط‌خواندنی.
- `templates/`: فایل XLSX ساختگی با Develop و Test و ۱ تا ۴ دیسک.
- [راهنمای کد و کامنت‌ها](docs/code-map.fa.md)، [مشارکت و توسعه](docs/contributing.fa.md)، [معماری و API](docs/architecture.md)، [راهنمای کاربری](docs/user-guide.fa.md)، [عملیات](docs/operations.fa.md)، [نسخه‌ها](docs/versioning.fa.md)، [امنیت](docs/security.fa.md).

نسخه تنها از فایل `VERSION` خوانده می‌شود. نسخه فعلی توسعه `0.1.0` است؛ هنوز release یا tag ساخته نشده است. پشتیبانی استقرار این تحویل: **Ubuntu 24.04، amd64**. arm64 بررسی نشده و installer آن را رد می‌کند.

برای استفاده عملیاتی باید تنظیمات HTTPS، DNS، پشتیبان بیرونی، مخزن انتشار، امضای release، دسترسی خواندن و helper مستقل بررسی و پیکربندی شوند. اجرای installer یا فعال‌کردن helper نیازمند فاز جداگانه استقرار است.
