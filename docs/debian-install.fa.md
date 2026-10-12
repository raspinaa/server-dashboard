# نصب InfraHub روی دبیان

این راهنما برای اجرای آینده روی سرور شما است. اسکریپت در این تحویل روی میزبان اجرا نشده است. هدف پشتیبانی: Debian 12 (Bookworm) و Debian 13 (Trixie)، معماری **amd64**. ARM فعلاً مسیر آزموده‌شده ندارد. راهنمای Ubuntu 24.04 و بسته‌های امضاشده همچنان در [راهنمای عملیات](operations.fa.md) است.

## چه چیزهایی نصب می‌شوند؟

پیش‌نیازهای میزبان: CA certificates، curl، git، openssl، Python 3، ابزارهای IP و DNS، Docker Engine، Buildx و Compose حداقل 2.24.4. بسته‌های Docker از مخزن رسمی با امضای apt دریافت می‌شوند. Python فقط برای ابزار نصب است؛ Django/Gunicorn، React/Nginx، MySQL 8.4 و Caddy داخل کانتینر اجرا می‌شوند. MySQL، Node، Nginx یا Certbot روی سیستم نصب نمی‌شود. Caddy گواهی را مدیریت می‌کند. DNS داخلی فقط اگر انتخاب کنید کانتینر جداگانه دارد. اسکریپت SSH، resolv.conf و فایروال را تغییر نمی‌دهد.

## دریافت نصب‌کننده

در صفحه GitHub نسخه سورس موردنظر، شناسه کامل ۴۰ کاراکتری commit را بردارید. `COMMIT` را با همان مقدار جایگزین کنید؛ branch متغیر مثل main نسخه استقرار محسوب نمی‌شود. هیچ Release منتشرشده‌ای فرض نشده است.

```bash
COMMIT=REPLACE_WITH_FULL_40_CHARACTER_COMMIT
curl --fail --proto '=https' --tlsv1.2 \
  "https://raw.githubusercontent.com/raspinaa/server-dashboard/$COMMIT/scripts/bootstrap-debian.sh" \
  -o bootstrap-debian.sh
# پیش از اجرای root، سورس دانلودشده را بخوانید و با نسخه مخزن مقایسه کنید.
bash bootstrap-debian.sh --help
bash bootstrap-debian.sh --stage check
```

Git و HTTPS انتقال و شناسه commit را بررسی می‌کنند؛ این مسیر جای امضای مستقل منتشرکننده را نمی‌گیرد. برای انتشارهای آینده، مسیر signed release در `scripts/install.py` و راهنمای عملیات است.

## نصب مرحله‌ای

ابتدا فقط ابزارهای موردنیاز نصب می‌شوند. اگر نرم‌افزار متعارض مانند docker.io وجود داشته باشد، حذف خودکار انجام نمی‌شود؛ مدیر باید تعارض را حل کند. Docker موجود حفظ می‌شود و وجود plugin و حداقل نسخه Compose بررسی خواهد شد.

```bash
sudo bash bootstrap-debian.sh --stage prerequisites --apply
sudo bash bootstrap-debian.sh --stage download --apply --commit "$COMMIT"
```

مرحله download تنها سورس را در `/opt/infrahub-source` دریافت می‌کند؛ هیچ سرویس برنامه‌ای شروع نمی‌شود. مخزن دیگر با `--repo OWNER/REPO` و مسیر دیگر با `--source-dir` انتخاب می‌شود. برای مخزن خصوصی، فایل token فقط‌خواندنی با مجوز 600/400 به `--token-file` بدهید؛ token را در URL یا فرمان ننویسید. این token فقط برای خواندن سورس است و در تنظیمات برنامه ذخیره نمی‌شود.

### دامنه عمومی و Let’s Encrypt

ابتدا رکورد A دامنه را روی IP عمومی سرور تنظیم کنید. اگر IPv6 ندارید، AAAA اشتباه را حذف کنید. دسترسی ورودی TCP 80/443 و خروجی HTTPS باید در شبکه فراهم باشد؛ این اسکریپت فایروال یا NAT را تغییر نمی‌دهد. ایمیل واقعی برای ACME لازم است.

```bash
sudo bash bootstrap-debian.sh --stage install --apply \
  --host inventory.example.com --tls letsencrypt --email admin@example.com --dns manual
```

Caddy درخواست و تمدید گواهی را انجام می‌دهد. DNS بررسی می‌شود، اما اسکریپت نمی‌تواند بدون دسترسی پنل DNS، رکورد عمومی بسازد؛ آن را در ارائه‌دهنده دامنه تنظیم کنید. پورت سفارشی با `--http`/`--https` ممکن است، ولی challenge عمومی همچنان به 80/443 یا NAT مناسب نیاز دارد. شکست صدور گواهی باعث بازگشت خودکار به HTTP نمی‌شود.

### شبکه داخلی و گواهی محلی

```bash
sudo bash bootstrap-debian.sh --stage install --apply \
  --host inventory.internal --tls local --dns local \
  --address 192.0.2.10 --bind 192.0.2.10
```

IP نمونه را با IP واقعی LAN عوض کنید. پورت TCP/UDP 53 باید روی همان IP آزاد باشد. DNS محلی فقط نام برنامه را پاسخ می‌دهد، recursion ندارد و DNS عمومی را منتشر نمی‌کند؛ کلاینت‌ها باید صریحاً از این DNS یا resolver داخلی با conditional forwarding استفاده کنند. فایل `/opt/infrahub/config/local-root.crt` فقط گواهی عمومی CA است؛ پس از بررسی اثرانگشت، روی دستگاه‌های مجاز به trust store اضافه کنید. کلید خصوصی CA در data/caddy می‌ماند و نباید توزیع شود. اسکریپت CA را خودکار در trust store میزبان نصب نمی‌کند.

### بدون گواهی

```bash
sudo bash bootstrap-debian.sh --stage install --apply \
  --host 192.0.2.10 --tls none --dns none
```

این انتخاب صریح HTTP است؛ داده ورود و اطلاعات ماشین در انتقال رمز نمی‌شوند. فقط برای شبکه آزمایشی/مورداعتماد یا پشت تونل مناسب استفاده کنید. DEBUG همچنان خاموش است؛ cookie secure و HSTS متناسب با HTTP غیرفعال می‌شوند. گزینه `none` به معنی گواهی جعلی یا خطای نادیده‌گرفته‌شده TLS نیست.

## اجرای یک مرحله‌ای و ادامه پس از خطا

می‌توانید همان گزینه‌ها را با `--stage all --apply --commit "$COMMIT"` اجرا کنید. رمز مدیر در ترمینال به‌صورت پنهان پرسیده می‌شود و در history/آرگومان ذخیره نمی‌شود. اجرای مجدد همان نسخه تنظیمات، دیتابیس، مدیر موجود و کلیدها را حفظ می‌کند؛ نسخه متفاوت باید از مسیر ارتقا اجرا شود. دایرکتوری ناشناخته موجود بازنویسی نمی‌شود. در شکست، کانتینرها و داده‌های موجود حذف نمی‌شوند؛ لاگ را بررسی و همان مرحله را تکرار کنید. سرویس‌ها با restart policy و Docker فعال، بعد از reboot بازمی‌گردند.

```bash
cd /opt/infrahub
sudo bash scripts/compose.sh "$PWD" ps
sudo bash scripts/compose.sh "$PWD" logs --tail 100
sudo bash scripts/backup.sh "$PWD" /YOUR_PROTECTED_BACKUP_DIRECTORY
```

فایل `.env` و `config/` تنظیمات خصوصی و مستقل از سورس هستند؛ پشتیبان شامل آنها و کلیدهاست و باید رمزگذاری و محدود شود. تنظیم site در `config/compose.site.yml` است و ابزار backup/restore/upgrade آن را حفظ می‌کند. تنظیم کاربران، پروژه‌ها و رمز حساب‌ها از داخل برنامه انجام می‌شود. ارتقای خودکار dashboard تا پیکربندی کلید امضای release و helper مجاز فعال نمی‌شود. قالب انتشار امضاشده فعلی Ubuntu 24.04 را اعلام می‌کند؛ پیش از فعال‌کردن ارتقای خودکار روی Debian، باید مسیر انتشار و بررسی سازگاری Debian نیز آماده شود. bootstrap نسخه اولیه را نصب می‌کند و جایگزین انتشار امضاشده ارتقا نیست.

## آفلاین و محدودیت‌های تأیید

نصب آفلاین به آماده‌سازی قبلی بسته‌های Debian/Docker و همه تصاویر برای amd64 نیاز دارد؛ مرحله prerequisites اینترنت می‌خواهد. روی دستگاه آماده‌سازی، `docker save` و روی سرور `docker load` استفاده کنید؛ دستورهای تفصیلی در راهنمای عملیات هستند. سورس دقیق commit را منتقل کنید و مطابق نصب دستی همان راهنما تنظیم و اجرا کنید. Let’s Encrypt آفلاین نیست؛ از local یا TLS سازمانی استفاده کنید.

بازبینی سورس، آزمون ساخت تنظیمات، حفظ کلیدها، syntax shell و رندر Compose در محیط ایزوله انجام می‌شود. نصب واقعی روی Debian خام، DNS عمومی، صدور/تمدید واقعی ACME و reboot سرور به اجرای مرحله آینده نیاز دارند؛ اینها در این مرحله انجام نشده‌اند.
