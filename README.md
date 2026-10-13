# InfraHub

InfraHub سامانه فارسی و راست‌به‌چپ برای مدیریت موجودی پروژه‌ها و ماشین‌های مجازی است. اگر مشخصات سرورها در فایل‌های Excel پراکنده است، این برنامه آنها را به یک موجودی مشترک، قابل ویرایش و قابل پیگیری تبدیل می‌کند.

## کاربرد برنامه

- تعریف پروژه، محیط‌های دلخواه مثل Develop، Test و Production و دسترسی اعضای هر پروژه.
- نگهداری مشخصات مستقل سرور، Application، نقش ماشین، CPU، RAM، تعداد دلخواه دیسک، OS، شبکه، IP، Subnet و Gateway.
- ورود XLSX با نگاشت ستون‌ها، اعتبارسنجی، پیش‌نمایش و تصمیم درباره تعارض‌ها پیش از ثبت تراکنشی.
- ویرایش تحت وب، ثبت کار انجام‌شده و نظر، مشاهده تاریخچه تغییرات و جلوگیری از بازنویسی ویرایش همزمان.
- داشبورد مدیریتی با انتخاب پروژه و محیط، جزئیات سرویس‌ها و نمودارهای مستقل منابع.
- نمایش مجموع منابع ثبت‌شده به تفکیک پروژه و محیط؛ خروجی Excel از آخرین اطلاعات و خروجی جداگانه فعالیت‌ها.
- مدیریت کاربران و نقش‌ها، حفاظت رمز ماشین‌ها با رمزگذاری و مجوز مستقل نمایش، کپی و خروجی.

گردش کار: **تعریف پروژه ← دریافت Excel ← اعتبارسنجی و تصمیم ← ورود اطلاعات ← ویرایش و فعالیت ← خروجی Excel**.

InfraHub به vCenter، ESXi یا ماشین‌ها متصل نمی‌شود و ماشین نمی‌سازد. مسیر پوشه vCenter فقط اطلاعات توصیفی پروژه است. نمودارها منابع تخصیص‌یافته در موجودی را نشان می‌دهند؛ مصرف زنده، سلامت زیرساخت یا ظرفیت آزاد نیستند.

## نصب و ارتقای آفلاین

برنامه روی سرور به اینترنت نیاز ندارد. ابتدا با یک فرمان، دبیان با اینترنت آماده می‌شود؛ سپس اتصال اینترنت لازم نیست و بسته کامل امضاشده را روی سرور کپی می‌کنید.

```bash
# یک‌بار با اینترنت، از پوشه بسته/سورس:
sudo bash prepare/scripts/prepare-server.sh --apply
# سپس از بسته کپی‌شده، بدون اینترنت:
sudo infrahub-install /srv/infrahub-package --public-key /srv/trusted-public.key --host YOUR_SERVER_IP --apply
```

برای سورس checkoutشده مسیر آماده‌سازی `scripts/prepare-server.sh` است. بسته شامل تصاویر برنامه، MySQL، Caddy و DNS اختیاری، سورس و wheelهای CLI است؛ روی سرور npm/pip اینترنتی یا build انجام نمی‌شود. HTTPS با CA محلی یا HTTP قابل انتخاب است؛ Let’s Encrypt برای مسیر آفلاین پشتیبانی نمی‌شود. بک‌اند و دیتابیس روی شبکه داخلی‌اند؛ درگاه وب و DNS اختیاری برای دسترسی LAN هستند. عملیات برنامه و updater دانلود اینترنتی ندارد.

[راهنمای کامل آفلاین](docs/offline.fa.md)، [نصب دبیان](docs/debian-install.fa.md) و [فرمان‌های مدیریت](docs/cli.fa.md). هدف: Debian 12/13 و Ubuntu 24.04، فقط amd64. فایل‌های source آماده‌اند؛ بسته عملیاتی منتشر یا روی سرور نصب نشده است.

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

## فرمان‌های مدیریت سرور

پس از نصب: `sudo infrahub backup`، `sudo infrahub update PACKAGE_DIRECTORY` و `sudo infrahub restore PATH --confirm`. [راهنمای فرمان‌ها و ارتقای آفلاین](docs/cli.fa.md).

## راهنماها و ساختار سورس

- [گزارش مدیریتی](docs/reports.fa.md)، [فرمان‌های مدیریت](docs/cli.fa.md).
- [راهنمای کاربری](docs/user-guide.fa.md)، [نصب Debian](docs/debian-install.fa.md)، [عملیات، پشتیبان و ارتقا](docs/operations.fa.md)، [امنیت](docs/security.fa.md).
- [راهنمای کد و کامنت‌ها](docs/code-map.fa.md)، [توسعه و بررسی‌ها](docs/contributing.fa.md)، [معماری و API](docs/architecture.md)، [نسخه‌ها](docs/versioning.fa.md).
- `backend/`: Django/DRF، مدل‌ها، مهاجرت MySQL و API.
- `frontend/`: React/TypeScript و رابط فارسی RTL.
- `deploy/` و `scripts/`: Compose، Caddy، DNS اختیاری، نصب، پشتیبان، بازیابی و ارتقا.
- `templates/`: XLSX نمونه ساختگی با Develop و Test و یک تا چهار دیسک.

نسخه برنامه از [VERSION](VERSION) خوانده می‌شود؛ نسخه توسعه فعلی 0.2.0 است. اعتماد کلید امضای بسته، helper مجاز ارتقا، DNS داخلی و گواهی محلی در مرحله استقرار انجام می‌شود.
