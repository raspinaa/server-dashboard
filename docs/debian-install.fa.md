# نصب دبیان

مسیر نصب برنامه اکنون آفلاین است. [راهنمای کامل](offline.fa.md) شامل آماده‌سازی یک‌فرمانی سرور با اینترنت، ساخت بسته روی ماشین متصل، نصب از فایل کپی‌شده و ارتقای آفلاین است.

```bash
sudo bash /srv/infrahub-package/prepare/scripts/prepare-server.sh --apply
sudo infrahub-install /srv/infrahub-package --public-key /srv/trusted-public.key --host YOUR_SERVER_IP --apply
```

فرمان اول فقط پیش‌نیازهای Debian 12/13 amd64 را با اینترنت آماده می‌کند. فرمان دوم بدون اینترنت نصب می‌کند. IP و مسیرها را با مقادیر واقعی جایگزین کنید. کلید عمومی باید از قبل مستقل مورد اعتماد باشد. رمز admin هنگام نصب پرسیده می‌شود. آماده‌سازی host در این فاز اجرا نشده است.
