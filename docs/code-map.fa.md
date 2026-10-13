# راهنمای خواندن کد InfraHub

این راهنما مسیر هر قابلیت و دلیل تصمیم‌های مهم را توضیح می‌دهد. کامنت‌ها و docstringهای داخل کد روی منطق کسب‌وکار، امنیت و تراکنش تمرکز دارند؛ توضیح بدیهی خط‌به‌خط جایگزین معماری نیست.

## مسیر درخواست

۱. React درخواست را با session cookie و CSRF token به `/api/` می‌فرستد. ۲. DRF هویت کاربر را بررسی می‌کند. ۳. `api.py` رکورد را فقط از scope مجاز کاربر انتخاب می‌کند و نقش/مجوز مستقل را می‌سنجد. ۴. سرویس inventory یا XLSX تغییر را اعتبارسنجی و تراکنشی ذخیره می‌کند. ۵. پاسخ عمومی هیچ رمز قابل‌بازیابی ندارد.

| فایل | مسئولیت و تصمیم مهم |
|---|---|
| `backend/config/settings.py` | MySQL/strict mode، timezone، کوکی/CSRF، upload/session policy؛ تولید بدون کلید معتبر شروع نمی‌شود |
| `backend/config/urls.py` | مسیرهای صریح API؛ endpoint عمومی برای shell یا فایل credential وجود ندارد |
| `backend/core/models.py` | کاربران، عضویت، پروژه/محیط/سرویس، UUID ماشین/دیسک، credential، تاریخچه، import/export و update/audit |
| `backend/core/security.py` | scope، نقش و مجوز مستقل، encryption و audit بدون secret |
| `backend/core/validation.py` | ظرفیت، IP، prefix/mask و تمایز error/warning بدون وابستگی PostgreSQL |
| `backend/core/inventory.py` | snapshot امن، whitelist فیلدها، optimistic version، قفل ردیف، تغییر دیسک و history اتمیک |
| `backend/core/xlsx.py` | حدود فایل/ZIP، header mapping، merged cells، preview، تصمیم صریح، apply اتمیک و export قالب‌دار |
| `backend/core/api.py` | login/logout/password، CRUD مجاز، نقش‌ها، import/export، credential و update queue |
| `backend/core/updates.py` | metadata مخزن ثابت، کانال stable، permission و قفل صف؛ اجرای deployment در این فایل نیست |
| `backend/core/middleware.py` | maintenance برای حفاظت از نویسندگان و cache policy پاسخ API |
| `frontend/src/api.ts` | CSRF، خطای 409/403، دانلود بدون ذخیره رمز در browser persistence و نمایش زمان تهران |
| `frontend/src/main.tsx` | کامپوننت‌های پروژه، موجودی، ویرایش، فعالیت، اعتبارنامه، ورود/خروج، دسترسی و تنظیمات |
| `frontend/src/style.css` | RTL، موبایل، dark/light، focus و جدول قابل پیمایش با نام سرور sticky |

## مجوزها چگونه اعمال می‌شوند؟

`scope` پیش از lookup، پروژه‌های مجاز را محدود می‌کند؛ بنابراین UUID پروژه دیگر به‌عنوان رکورد قابل مشاهده برگردانده نمی‌شود. `require` حداقل نقش و مجوز مستقل را جدا بررسی می‌کند. داشتن credential_view به‌تنهایی عضویت پروژه ایجاد نمی‌کند. مدیر سیستم یک استثنای صریح مدیریتی است. منطق permission در UI فقط برای usability است و جای بررسی backend را نمی‌گیرد.

مسیر credential از ماشین معمولی جداست. `snapshot` فقط has_credential را می‌فرستد. reveal/copy/edit/export مجوز و audit مستقل دارند. Fernet مقدار ذخیره‌شده را احرازشده رمز می‌کند؛ کلید باید جدا از DB و سورس نگهداری شود. audit فقط شناسه و نتیجه می‌گیرد؛ payload کامل درخواست نباید به آن داده شود.

## ویرایش و تاریخچه

`save_machine` ردیف را با select_for_update قفل و نسخه ارسالی را مقایسه می‌کند. شکست نسخه، خطای 409 است و هیچ overwrite انجام نمی‌شود. ذخیره فیلدها، دیسک‌ها، Activity و Change در یک transaction است. برای جابه‌جایی ترتیب دیسک، ابتدا ترتیب موقت خارج از محدوده کاربر تخصیص داده می‌شود تا unique constraint هنگام swap برخورد نکند.

در PATCH نبودن کلید disks یعنی حفظ دیسک‌ها؛ disks=[] حذف صریح دیسک‌هاست. مقدار قبلی/جدید دیسک با UUID در Change می‌ماند. حذف پروژه، محیط و کاربر در روابط مهم PROTECT است؛ archiving برای حفظ inventory/history استفاده می‌شود. تغییر رمز فقط رویداد redacted می‌سازد.

## ورود Excel

`load_safe` پیش از parse، حجم و ابعاد ZIP/workbook و macro/external link را بررسی می‌کند. detection فقط پیشنهاد mapping است؛ کاربر می‌تواند mapping را اصلاح کند. مقادیر Environment/Application تنها در محدوده merged cell منتقل می‌شوند. ردیف جداکننده ماشین نمی‌سازد و ظرفیت خالی/صفر دیسک خیالی نمی‌سازد.

`preview` inventory را تغییر نمی‌دهد؛ snapshot، نسخه نامزدها و نتیجه اعتبارسنجی ذخیره می‌شود. فایل اصلی و credential احتمالی ورودی encrypted هستند. ImportValidation سابقه نسخه‌های preview را نگه می‌دارد.

`apply` batch و پروژه را قفل می‌کند، نسخه preview و نسخه هر ماشین هدف را بررسی می‌کند و برای هر ردیف تصمیم صریح لازم دارد. بدون UUID، حتی یک نامزد تطبیق باید انتخاب شود؛ IP شناسه نیست. سیاست فیلدها و دیسک‌ها جداست. در حالت replace حذف دیسک غایب صریح است؛ merge دیسک اضافه وب را حفظ می‌کند. رکورد غایب از فایل هرگز حذف نمی‌شود. شکست یک ردیف، کل تغییرات همان batch را rollback می‌کند. ImportDecision به batch، نسخه preview، کاربر و ماشین نهایی مرتبط است.

## خروجی Excel

`export_inventory` مقدار فعلی DB را می‌خواند، ستون‌های دیسک را پویا می‌سازد، Subnet را مستقل نگه می‌دارد و UUID/متادیتای دیسک را مخفی ذخیره می‌کند. ساختار فایل اصلی در صورت وجود مبناست؛ بدون آن تقریب مستند تولید می‌شود. escaping متن با marker نسخه‌دار workbook امکان roundtrip متن شبیه formula را بدون اجرای formula فراهم می‌کند. credential export در API دوباره مجوزسنجی می‌شود، پیش‌فرض خاموش است و فایل خروجی روی سرور نگه داشته نمی‌شود.

## کامپوننت‌های رابط

- `App`: session و پروژه انتخابی؛ generation counter مانع اعمال پاسخ دیررس حساب قبلی می‌شود.
- `Projects` / `EnvironmentRow`: تعریف و بایگانی پروژه/محیط با version.
- `Inventory`: overview، نمودارهای مستقل، environment tabs، pagination و accordion.
- `MachineEditor`: فیلدهای مستقل و دیسک‌های متغیر؛ هشدار تغییر ذخیره‌نشده و handling نسخه stale.
- `MachineDetail`: فعالیت، history، comment revisions و فرم مشخصات.
- `InlineCredential` / `CredentialControls`: درخواست مجاز در لحظه، نمایش ۱۵ ثانیه‌ای، پاک‌شدن در navigation و fallback کپی.
- `Imports` / `Exports`: mapping/preview/decisions و دریافت inventory/activity XLSX.
- `Access` / `AuditPage` / `Settings`: مدیریت حساب/عضویت، audit فقط‌خواندنی، session policy و وضعیت update.

## نصب و به‌روزرسانی

`install.py` پیش‌فرض فقط plan است؛ --apply مسیر استقرار آینده است. تشخیص OS/arch، بررسی امضا و checksum، حفاظت از نصب موجود و ساخت secret یکتا انجام می‌شود. ابزارهای backup/restore داده و کلید را حفظ می‌کنند؛ restore confirmation صریح می‌خواهد.

`release.py` بسته محلی می‌سازد و امضا می‌کند، upload نمی‌کند. `build_offline.py` تصاویر و wheelها را روی ماشین متصل جمع می‌کند؛ `prepare-server.sh` تنها پیش‌نیازهای سرور را با اینترنت آماده می‌کند؛ `offline_install.py` نصب را از بسته محلی امضاشده انجام می‌دهد. دریافت GitHub در runtime حذف شده است. `upgrade.py` قفل، integrity، preflight، backup، maintenance، staging، migrations، restart و health را با دستورهای ثابت اجرا می‌کند؛ rollback schema خودکار نیست. `update_helper.py` بیرون HTTP اجرا می‌شود و version allowlisted می‌گیرد؛ وب Docker socket ندارد و state به‌روزرسانی را فقط read-only می‌بیند.

برای جزئیات عملیاتی و محدوده آزمون‌ها، [عملیات](operations.fa.md)، [امنیت](security.fa.md)، [معماری/API](architecture.md) و [گزارش بررسی](verification.md) را بخوانید.
