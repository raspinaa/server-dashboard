# راهنمای توسعه و ثبت تغییرات

## شروع

ابتدا README و code-map.fa.md را بخوانید. Python 3.12، Node 24 و MySQL 8.4 توسعه لازم است. dependencies از requirements.lock با hash و package-lock.json با npm ci نصب می‌شوند. فایل .env.example فقط placeholder است؛ .env، .env.dev، secret/key، dump، backup و خروجی build وارد Git نمی‌شوند. داده نمونه و accountهای CI/dev صرفاً ساختگی‌اند و برای production معتبر نیستند.

## تغییرات backend

permission جدید را ابتدا در security و endpointهای مربوط اعمال و سپس در UI منعکس کنید. querysetهای scoped را حذف نکنید. تغییر inventory باید از سرویس تراکنشی عبور کند؛ version و history را دور نزنید. رمز را وارد snapshot، logging، exception detail یا تاریخچه نکنید. تغییر مدل migration صریح می‌خواهد. رفتار case/accent-sensitive نام‌ها و عدم uniqueness نام/IP را حفظ کنید.

## تغییرات Excel

mapping و merged ranges را به fixtureهای واقعی XLSX اضافه کنید. UUID، disk identity، blank/zero capacity، formula escaping و workbook roundtrip را بررسی کنید. سیاست جدید conflict باید در preview قابل مشاهده و در apply صریح باشد. درخواست caller نباید snapshot نسخه مبنا یا شناسه پروژه را جایگزین داده سرور کند.

## تغییرات UI

زبان فارسی و RTL، label قابل دسترس، keyboard/focus، موبایل و dark/light حفظ شوند. فیلدهای منابع، Application/VMs و IP/Subnet/Gateway را ترکیب نکنید. secret را در localStorage/sessionStorage یا bundle قرار ندهید. permission backend همچنان مرز امنیت است. selectorهای browser test را با accessible name و پس از تکمیل عملیات async انتخاب کنید؛ timeout یا انتظار ثابت را جای assertion رفتاری نگذارید.

## بررسی پیش از commit

از ریشه طبق README database development را آماده کنید و check/test را اجرا کنید؛ سپس در frontend: npm run typecheck، npm test، npm run build و npm run test:e2e. برای تغییرهای عملیات، fixtureهای isolated installer/backup/update و bash -n لازم‌اند؛ installer واقعی روی host توسعه اجرا نشود. گزارش test باید passed/failed/skipped/unrun را جدا بگوید. MySQL integration را با SQLite جایگزین نکنید.

CI در .github/workflows/checks.yml فقط تست و build انجام می‌دهد؛ deploy، upload image یا publish release ندارد. نتیجه CI در GitHub باید پس از اجرا بررسی شود؛ گزارش آزمون‌های محلی ادعای موفقیت CI نیست.

## commit و release

هر batch منطقی یک commit قابل بازبینی داشته باشد و پیام آن مشکل/رفتار نهایی را توضیح دهد. commit سورس با release فرق دارد. نسخه از VERSION خوانده می‌شود؛ هنگام تغییر نسخه package.json و lock metadata نیز هماهنگ و CHANGELOG به‌روز شود. tag/release و artifact signing فقط در مرحله انتشار مجاز، با release-notes template و migration/backup guidance انجام می‌شوند. کلید خصوصی امضا در مخزن یا host وب نباشد.

برای نصب، عملیات و integrationهای هنوز تأییدنشده به operations.fa.md و verification.md مراجعه کنید. در این مرحله OIDC/MFA و secret-store adapter قابلیت آینده‌اند؛ toggle یا claim اجرایی برای آن‌ها اضافه نکنید مگر پیاده‌سازی و آزمون شوند.
