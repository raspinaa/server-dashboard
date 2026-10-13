# عملیات InfraHub

[نصب و ارتقای آفلاین](offline.fa.md) مسیر پشتیبانی‌شده است. سرور یک‌بار با اینترنت آماده می‌شود؛ بسته برنامه روی سرور build/download نمی‌شود. فقط amd64 و Debian 12/13 یا Ubuntu 24.04 برای payload اعلام شده‌اند؛ اسکریپت یک‌فرمانی آماده‌سازی فعلی Debian 12/13 را پشتیبانی می‌کند. Ubuntu باید Docker/Compose و Python/venv سازگار را با روش مدیریتی خودش آماده کند.

داده‌ها در data/mysql، data/uploads، data/caddy و config/.env/state نگهداری می‌شوند. backend بدون root، filesystem خواندنی و با mountهای حداقلی اجرا می‌شود. شبکه backend و database داخلی است و image pull_policy=never دارد. پروکسی و DNS برای انتشار پورت در LAN به bridge دسترسی وصل می‌شوند؛ masquerade خروجی آن غیرفعال است. این تنظیم جای سیاست شبکه یا قطع اینترنت میزبان را نمی‌گیرد. وب هیچ Docker socket ندارد. رمز ماشین در دیتابیس ciphertext است و CREDENTIAL_KEY خارج از دیتابیس نگهداری می‌شود؛ فقدان کلید، بازیابی را ناممکن می‌کند. .env و کلیدها وارد Git نشوند.

```bash
cd /opt/infrahub
sudo bash scripts/compose.sh "$PWD" ps
sudo bash scripts/compose.sh "$PWD" logs --tail 100
sudo infrahub backup
```

backup تاریخ‌دار شامل تنظیمات و کلیدهاست؛ به ذخیره‌ساز محدود بیرونی منتقل و رمزگذاری کنید. restore صریح، دیتابیس برنامه را با DROP DATABASE بازسازی می‌کند؛ نیازمند مجوز مربوط است. قبل از ارتقا فضای تصاویر، artifact و snapshot کافی فراهم کنید. ناسازگاری migration نیازمند بازگردانی backup است؛ rollback خودکار برای MySQL وعده داده نمی‌شود. برای پایش سلامت فقط endpoint داخلی آماده‌بودن برنامه داریم؛ نمودارها از inventory هستند.

HTTPS آفلاین با CA محلی است؛ گواهی عمومی root را پس از بررسی اثرانگشت به دستگاه‌های مجاز اعتماد دهید. کلید خصوصی CA فقط در سرور و backup محافظت‌شده باقی بماند. DNS داخلی فقط نام برنامه را پاسخ می‌دهد و resolver عمومی/recursion نیست. SSH و firewall توسط اسکریپت تغییر نمی‌کنند.

برای helper اختیاری dashboard از deploy/infrahub-update.service استفاده شود؛ بررسی بسته و staging توسط infrahub stage صورت می‌گیرد. helper فقط نسخه SemVer و عملیات ثابت روی بسته‌های محلی را می‌پذیرد. فعال‌سازی systemd و permission انجام update روی سرور واقعی به مرحله استقرار نیاز دارد.

حذف سرویس: ابتدا backup و سپس Compose down بدون --volumes. داده‌ها و config را حفظ کنید؛ حذف /opt/infrahub یا data به‌صورت خودکار در uninstall انجام نمی‌شود. برای بازیابی رمز مدیر، فرمان Django changepassword داخل backend با دسترسی مدیریتی اجرا شود؛ رمز در آرگومان نباشد.
