# نصب، نگهداری و به‌روزرسانی (فاز آینده)

این اسناد مجوز اجرا نیستند. در فاز سورس هیچ installer، سرویس host یا اتصال عملیاتی اجرا نشده است.

## تنظیمات

`.env.example` فقط placeholder است. در تولید DEBUG=0، کلید تصادفی Django، Fernet مستقل، رمزهای متفاوت MySQL، hosts، trusted origins، domain، پورت‌ها، session/upload policy و محل persistent storage لازم است. Compose دیتابیس را به host منتشر نمی‌کند؛ داده در `data/mysql`، فایل رمزگذاری‌شده در `data/uploads`، گواهی Caddy در `data/caddy` و پیشرفت/maintenance در `state` باقی می‌ماند. `secrets` برای فایل credential خواندن release است. این پوشه‌ها نباید وارد Git یا بسته انتشار شوند. در نصب دستی uploads مالک UID 10001 و writable؛ state مالک helper، پوشه اصلی خواندنی و mount وب read-only، سورس read-only و `.env` با mode 0600 باشد.

## آنلاین

روی Ubuntu 24.04 amd64 با DNS و اجازه دسترسی به Docker apt، image registry، PyPI/npm و GitHub release؛ کلید عمومی Ed25519 را از کانال مورداعتماد مستقل دریافت کنید. Python 3.12 و cryptography/requests در venv مخصوص installer لازم است؛ installer به system Python بسته pip اضافه نمی‌کند. فایل نصب باید از همین سورس بازبینی‌شده یا کانال معتبر باشد، نه pipe اینترنت به shell.

```bash
# فقط نمایش برنامه؛ تغییری نمی‌دهد:
helper-venv/bin/python scripts/install.py --version X.Y.Z --repository OWNER/REPO --public-key /secure/release-public.key
# در فاز استقرار و پس از مجوز مستقل، --apply اضافه می‌شود.
```

installer OS/arch/privilege را بررسی می‌کند، manifest امضاشده و checksum را قبل از استخراج می‌سنجد، Docker را از apt repository امضاشده رسمی نصب می‌کند، domain/ports/admin می‌پرسد، کلیدهای یکتا ایجاد، مهاجرت و prompt مخفی مدیر را اجرا، Caddy HTTPS و health checks را راه‌اندازی می‌کند. firewall یا SSH را تغییر نمی‌دهد. نصب دوباره با `.env` یا data موجود بدون تغییر بازمی‌گردد؛ target غیرخالی رد می‌شود. بعد از شکست، state/config را حذف نکنید؛ علت را رفع و مراحل manual Compose را ادامه دهید. این نسخه reset/overwrite خودکار ندارد.

گواهی عمومی به DNS صحیح و دسترسی HTTP-01/TLS-ALPN روی 80/443 نیاز دارد؛ mapping پورت سفارشی به‌تنهایی آن شرط را برطرف نمی‌کند. نصب IPv4 با --tls-cert و --tls-key و گواهی معتبر برای SAN دقیق IP پشتیبانی می‌شود؛ بدون گواهی هرگز به HTTP ناامن fallback نمی‌کند. زنجیره گواهی و trust client باید توسط مسئول استقرار فراهم شود. برای تنظیم دستی: Caddyfile با `tls /certs/cert.pem /certs/key.pem` و mount read-only certificate مورداعتماد تنظیم شود؛ ALLOWED_HOSTS/IP و trusted origins باید HTTPS دقیق باشند. گواهی self-signed نیازمند trust صریح client است و نباید Secure cookies خاموش شوند.

## آفلاین

روی ماشین build مجاز برای amd64 تصاویر backend/frontend را از Dockerfiles بسازید؛ `docker save` تصاویر backend/frontend همراه mysql:8.4.11 و the digest-pinned Caddy image from compose.prod.yml را در `deploy/offline/images.tar` قرار دهید. تصاویر برنامه با نام‌های infrahub-backend:X.Y.Z و infrahub-frontend:X.Y.Z ذخیره شوند؛ APP_VERSION در پیکربندی همان نسخه است. Compose آفلاین با --no-build و --pull never اجرا می‌شود. بسته نهایی را با release.py دوباره امضا کنید. Docker/Compose و venv installer باید قبلاً نصب باشند. `--offline --artifact ... --manifest ... --signature ... --public-key ... --version ...` همراه --apply در فاز مجاز اجرا شود. شبکه، pull/build یا دانلود Docker در حالت آفلاین نباید لازم باشد. فایل image tar زیر checksum و امضای کل بسته پوشش داده می‌شود. بسته/تصویر آفلاین آماده و منتشرشده در این تحویل وجود ندارد.

## پشتیبان و بازیابی

`bash scripts/backup.sh INSTALL_ROOT UNIQUE_BACKUP_DIRECTORY`، mysqldump با single-transaction و checksum می‌سازد و uploads/config/keys/version/state را ذخیره می‌کند. خروجی محرمانه با umask 077 است؛ رمز را در آرگومان command نمی‌گذارد. پشتیبان را رمزگذاری و بیرون host نگهدارید، retention و آزمون دوره‌ای recovery تعریف کنید. پشتیبان عادی snapshot تراکنشی دیتابیس دارد؛ برای سازگاری کامل هنگام تغییر فایل‌های configuration، maintenance و توقف نویسندگان الزامی است. helper قبل از پشتیبان نویسندگان را متوقف می‌کند.

`bash scripts/restore.sh INSTALL_ROOT BACKUP_DIRECTORY --confirm-restore` checksum را می‌سنجد، maintenance می‌گذارد، پشتیبان قبل از بازیابی می‌گیرد، نویسندگان را متوقف، فایل/کلیدها و dump را بازیابی و health checks اجرا می‌کند. برای recovery باید رمز root دیتابیس جاری با backup سازگار و image/code نسخه backup آماده باشد. اگر دیتابیس root password یا schema بین نسخه‌ها متفاوت است، recovery را روی instance جدید و نسخه backup اجرا کنید؛ ابزار ادعای تغییر خودکار root key ندارد. اسکریپت داده جاری را بازنویسی می‌کند و confirmation اجباری دارد. شکست maintenance را نگه می‌دارد.

## ارتقای دستی و dashboard

منبع انتشار فقط repository تنظیم‌شده و stable SemVer tag است، نه main/latest branch. release باید `manifest.json`, `manifest.sig`, `infrahub-X.Y.Z.tar.gz` داشته باشد. manifest شامل version، OS/arch/MySQL و SHA-256 بسته است و با کلید Ed25519 مستقل امضا می‌شود. private repo token فقط خواندنی از فایل 0600 استفاده می‌شود؛ token در URL، args، log یا bundle نیست.

`upgrade.py --root ... --artifact ... --manifest ... --signature ... --public-key ... --version X.Y.Z` امضا/نسخه/فضا/health را بررسی، قفل می‌گیرد، maintenance فعال، نویسندگان را متوقف و backup می‌سازد، stage را امن استخراج، فقط سورس برنامه را جایگزین، images را build، migrations را اجرا و health را می‌سنجد. داده، کاربران، تاریخچه، فایل‌ها، config و کلیدها حفظ می‌شوند. پس از failure maintenance و backup باقی می‌ماند. database migration برگشت‌ناپذیر rollback خودکار ندارد؛ نسخه قبلی سورس + بازیابی dump در recovery مستند لازم است. migrationهای compatible را ترجیح دهید.

dashboard check فقط metadata می‌گیرد. برای اجرا لازم است مسئول استقرار helper-venv، کلید عمومی، credential فقط‌خواندنی، پوشه staging انتشار و سرویس `deploy/infrahub-update.service` را جداگانه پیکربندی کند؛ UPDATE_EXECUTION_ENABLED تنها پس از آزمایش helper=1 شود. helper روی host مورداعتماد Docker اختیار دارد ولی وب socket ندارد. queue فقط version می‌پذیرد؛ root/repository/commands از HTTP پذیرفته نمی‌شوند. عملیات خارج HTTP و همراه journal پایدار است. شکست دسترسی GitHub خطای قابل‌فهم و audit می‌دهد. retry پس از تشخیص علت و بررسی backup انجام شود.

## حذف

در فاز مجاز `docker compose --env-file .env -f deploy/compose.prod.yml down` سرویس‌ها را متوقف می‌کند؛ از `down -v`، حذف data، `.env` و کلید استفاده نکنید. سرویس helper opt-in را جداگانه متوقف کنید. حذف واقعی داده نیازمند تأیید صریح و پشتیبان بازیابی‌شده است.

## عیب‌یابی

- 403 ورود: ابتدا GET session برای CSRF، hosts/origins/HTTPS و اعتبار جلسه را بررسی کنید.
- 409: preview یا فرم را تازه کنید؛ تغییر دیگران را overwrite نکنید.
- credential decrypt: کلید اصلی پشتیبان را بررسی کنید؛ مقدار جدید تصادفی جایگزین نکنید.
- MySQL اتصال: healthcheck، نام سرویس db، grants و strict mode را بررسی کنید؛ public DB port لازم نیست.
- import خطا: ردیف/نگاشت، merged ranges، ظرفیت و mask را بررسی کنید؛ فایل اصلاح‌شده دوباره upload شود.
- update شکست: state journal، backup و maintenance؛ logهای حساس را در UI کپی نکنید.

پیکربندی helper در `helper.json` حفاظت‌شده شامل `repository` و در صورت خصوصی‌بودن `read_token_file` است؛ با RELEASE_REPOSITORY وب یکسان و فقط توسط مسئول استقرار قابل‌ویرایش باشد. helper هنگام نبود artifact آفلاین، همان release پایدار را دانلود می‌کند و سپس امضا را می‌سنجد. journal به‌صورت atomic در state ثبت می‌شود. restart helper اجرای نیمه‌تمام را failed می‌کند؛ retry پس از بررسی backup به‌صورت forward-only و با حفظ backup اصلی ممکن است. کد ارتقا کلید و داده را تغییر نمی‌دهد؛ فقط APP_VERSION را هماهنگ می‌کند. helper-venv با scripts/requirements.lock آماده شود.

installer گواهی/کلید TLS ورودی را از نظر تطابق کلید و SAN بررسی و در data/tls با mode 0600 ذخیره می‌کند؛ رمز عبور کلید PEM در این نسخه پشتیبانی نمی‌شود. backend این پوشه را mount نمی‌کند. گواهی IP باید از نظر مرورگر/سازمان مورداعتماد باشد. پشتیبان TLS و helper.json/public key را نیز در صورت وجود حفظ می‌کند.

اگر MYSQL_HOST از db متفاوت است، ابزار dump/restore از همان host/port با MYSQL_USER/PASSWORD استفاده می‌کند؛ این user باید مجوزهای backup/restore (از جمله routines/events) را داشته باشد. هیچ اتصال بیرونی در فاز سورس آزمایش نشده است. TLS و CA برای MySQL بیرونی باید در client config حفاظت‌شده تنظیم و اتصال امن پیش از فعال‌کردن update helper تأیید شود؛ baseline این تحویل شبکه خصوصی Compose است.
