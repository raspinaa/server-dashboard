# گزارش بررسی سورس — ۲۰ مهر ۱۴۰۵ / 2026-10-12

این گزارش نتایج مرحله توسعه اولیه در محیط محلی و ایزوله را ثبت می‌کند. در زمان آن آزمون‌ها، استقرار روی سرور، اجرای installer عملیاتی، نشر GitHub/release یا بارگذاری تصویر انجام نشده بود. پس از آن مرحله، سورس و مستندات برای ثبت در مخزن `raspinaa/server-dashboard` آماده شدند؛ نتایج جدول زیر مربوط به همان اجراهای ثبت‌شده هستند، نه نتیجه CI بعد از push. فایل‌های مرجع Windows در این محیط در دسترس نبودند؛ رابط از مشخصات پیاده‌سازی شد.

## نتیجه اجراهای واقعی

| بررسی | نتیجه |
|---|---|
| Django system check | بدون خطا و هشدار |
| Migration consistency (`makemigrations --check --dry-run`) | هیچ تغییر مدل ثبت‌نشده |
| مهاجرت‌ها روی MySQL 8.4.11 | هر سه migration برنامه و migrations Django اجرا شدند |
| Backend/operations suite | **74 passed** روی MySQL واقعی، بدون SQLite و بدون skipped در اجرای opt-in |
| MySQL dump/restore | DB ساختگی مجزا: dump، تغییر داده، restore و بررسی مقدار قبلی؛ فایل/کلید ساختگی نیز بازیابی شد |
| Frontend typecheck + production build | موفق |
| Vitest | **3 passed** (محدوده کوچک presentation؛ اعتبارسنجی اصلی UI در مرورگر) |
| Playwright | **6 passed**: سه گردش کار در desktop و mobile با backend/MySQL واقعی |
| Docker builds | هر دو Dockerfile موفق؛ نصب با hash locks، TLS و امضای apt حفظ شد |
| Gunicorn container | non-root/read-only؛ درخواست authentication و overview واقعی با ۴ ماشین و ۴۰۰ GB دیسک نمونه موفق |
| Frontend container | non-root/read-only؛ HTTP 200، عنوان InfraHub و CSP بررسی شد |
| Compose configs | `config --quiet` برای development و production موفق |
| Caddy config | validation موفق با domain ساختگی `.invalid`؛ Nginx 1.30.5 و Caddy 2.11.7 از stable imageهای digest-pinned بررسی شدند |
| Source syntax | compileall، Ruff undefined-name check و shell syntax موفق |
| Visual inspection | screenshots موجودی desktop/mobile بازبینی شدند؛ تصاویر ورود Excel نیز در docs/screenshots ذخیره شدند |

آزمون‌های backend شامل role/project isolation، CSRF/login/session/password، آخرین مدیر، رمزگذاری/redaction/revocation، دیسک متغیر و ترتیب، ویرایش stale، شبکه/Subnet، history/revisions، ادغام سلول، HDD تکراری، صفر/خالی/ورودی نامعتبر، ambiguity، add-only، conflict و حفظ دیسک، rollback تراکنشی، stale preview، UUID/disk roundtrip، grouping/format، formula text roundtrip، totals، update permission/lock/signature/tampering/failed health/retry و حفاظت از keys/config است.

آزمون‌های browser شامل ورود/خروج، جدول مستقل، فعالیت، ویرایش CPU، دریافت XLSX، ایجاد پروژه، upload/mapping/preview/apply واقعی template، چهار دیسک، ساخت حساب/عضویت Viewer، منع ویرایش/ورود Viewer، تغییر اعتبارنامه ساختگی، پنهان‌شدن بعد از ۱۵ ثانیه، fallback کپی و redaction inventory/audit است. secret واقعی استفاده نشد و screenshots شامل رمز بازیابی‌شده نیستند.

در آزمون backup/restore، دستورات DB به container ساختگی واقعی هدایت شدند؛ stop/start سرویس برنامه و health deployment **mock** بودند. در آزمون update، runner و health responses **mock** بودند؛ filesystem staging، امضا، checksum، lock، journal، failure و retry واقعی و ایزوله بودند. installer فقط plan و idempotency با OS/privilege/command mocks بررسی شد؛ هیچ apt/systemctl/install روی host اجرا نشد.

## بازاجرای محلی

از ریشه پروژه، با MySQL تست disposable روی 33306:

```bash
MYSQL_SCRIPT_CONTAINER=infrahub-dev-mysql .venv/bin/python -m pytest -q
MYSQL_USER=root MYSQL_PASSWORD=isolated-test-root MYSQL_PORT=33306 .venv/bin/python scripts/dev.py check
DJANGO_SETTINGS_MODULE=config.test_settings .venv/bin/python backend/manage.py makemigrations --check --dry-run
```

بدون `MYSQL_SCRIPT_CONTAINER` آزمون dump/restore خاص container یک skip اعلام می‌کند؛ این skip نباید passing محسوب شود. defaults آزمون فقط synthetic هستند. برای MySQL development Compose مستند README، نام container همان محیط و port/password توسعه را با environment override کنید؛ روی دیتابیس عملیاتی pytest اجرا نکنید.

برای UI ابتدا migrate/seed/server طبق README، سپس:

```bash
cd frontend
npm ci
npm run typecheck
npm test
npm run build
# در این محیط Chromium از قبل موجود بود:
CHROMIUM_EXECUTABLE=/usr/bin/chromium npm run test:e2e
# در محیط تازه با دسترسی به CDN رسمی:
npx playwright install chromium
npm run test:e2e
```

دانلود Playwright CDN در این محیط 403 شد؛ مرورگر موجود Chromium استفاده شد. Docker build container ابتدا DNS و CA proxy را نداشت؛ با mapping محلی proxy و public CA معتبر از trust store محیط، نصب انجام شد. هیچ `--trusted-host`، `strict-ssl=false`، حذف signature یا checksum bypass استفاده نشد. Dockerfiles ورودی اختیاری BuildKit `enterprise_ca` دارند؛ certificate فقط public CA است. Node/Python/Nginx/Caddy digestها و dependency locks باید در تغییرات امنیتی آینده بازبینی و refresh شوند.

## موارد اجرا نشده و گام فاز بعدی

- **اجرای واقعی installer روی Ubuntu 24.04، daemon startup پس از reboot و helper systemd:** عمداً اجرا نشد. روی VM disposable و فقط در فاز استقرار مجاز، بسته امضاشده و trusted public key را آماده و فرمان زیر را اجرا/بررسی کنید:
  `helper-venv/bin/python scripts/install.py --version X.Y.Z --artifact /secure/infrahub-X.Y.Z.tar.gz --manifest /secure/manifest.json --signature /secure/manifest.sig --public-key /secure/release-public.key --apply`.
- **DNS/ACME/HTTPS عمومی و IP certificate trust:** فایل Caddy فقط validate شد؛ هیچ domain یا گواهی واقعی استفاده نشد. پس از پیکربندی مجاز: `bash scripts/health.sh INSTALL_ROOT` و درخواست HTTPS `/api/health/` از یک client مستقل با certificate verification. برای IP، installer به `--tls-cert` و `--tls-key` با SAN دقیق نیاز دارد.
- **بسته تصویر آفلاین:** source مسیر load بدون build/pull دارد، ولی بسته واقعی آماده نشد. در فاز مجاز images مربوط به Compose را save و داخل artifact امضاشده قرار دهید؛ installer را با `--offline` در VM قطع از اینترنت آزمایش کنید.
- **GitHub/private release access و انتشار:** فقط metadata logic با mock و signed artifact fixtures بررسی شد. repository/channel/public key/read-only credential باید بعداً تنظیم شوند. فرمان read-only آینده: `helper-venv/bin/python scripts/fetch_release.py --repository OWNER/REPO --version X.Y.Z --destination /secure/staging --token-file /secure/read-only-token`؛ credential value هرگز آرگومان نیست.
- **host-side dashboard upgrade واقعی و migration بین دو release واقعی:** runner mock بود؛ helper نیازمند بررسی privileges، helper.json، public key، safe staging و فعال‌سازی مجاز است. فرمان دستی آینده: `helper-venv/bin/python scripts/upgrade.py --root INSTALL_ROOT --artifact ... --manifest ... --signature ... --public-key ... --version X.Y.Z`. database rollback خودکار ادعا نشده است.
- **MySQL بیرونی و TLS آن:** app/client configuration قابل تنظیم است، اما هیچ اتصال بیرونی، credential یا دیتابیس واقعی آزموده نشد؛ backup/restore grants و secure transport باید روی integration مجاز بررسی شوند.
- **arm64 و دیگر معماری‌ها:** آزمایش نشدند؛ installer فقط amd64 می‌پذیرد. وجود multiarch image به معنی تأیید برنامه روی همه معماری‌ها نیست.
- **OIDC/MFA/secret-store adapter:** مرز integration و وضعیت «پیکربندی نشده/آینده» مستند است؛ قابلیت اجرایی یا امنیت اعمال‌شده ادعا نمی‌شود.

این تست‌ها جایگزین بازبینی امنیتی مستقل و acceptance/restore drill روی محیط هدف نیستند. سقف import محدود و synchronous است؛ workloadهای بالاتر از ۱۰٬۰۰۰ ردیف به worker جداگانه آینده نیاز دارند. هیچ formatting fidelity کامل از screenshot یا همه اشیای سفارشی workbook ادعا نمی‌شود.

## Debian bootstrap source update — 2026-10-12

Result: **91 tests passed**, including opt-in disposable-MySQL backup/restore. Local checks for this change: MySQL-backed backend/operations suite, isolated dump/restore, transport/configuration tests, shell syntax, Python compilation and `git diff --check`. Three Caddy configurations (ACME, internal CA, HTTP) passed validation in network-isolated containers. Local-DNS image built for amd64 with verified apt packages and its generated dnsmasq configuration passed syntax validation. Site/DNS Compose override rendered successfully with `docker compose config --quiet`.

This change does not modify frontend source; the prior frontend type/build/browser results apply to the unchanged UI. Fresh Debian 12/13 installation, host apt/service changes, live DNS queries from clients, public DNS provisioning, real ACME issuance/renewal, client CA installation and reboot persistence were **not executed**. They require the later deployment phase, using `docs/debian-install.fa.md`. Initial pinned-source bootstrap is distinct from the existing Ubuntu-specific signed-release updater; Debian signed-release compatibility needs configuration/source integration before dashboard updates are enabled.

Reproduce safe checks: `python -m pytest -q`, `bash -n scripts/bootstrap-debian.sh`. For disposable MySQL dump/restore testing only: `MYSQL_SCRIPT_CONTAINER=YOUR_DISPOSABLE_MYSQL_CONTAINER python -m pytest tests/test_backup_integration.py -q`. Do not point integration tests at production data.

## Installer permissions follow-up — 2026-10-12

95 MySQL-backed tests passed with opt-in isolated backup/restore. Permission tests cover private modes, intended ownership calls, repeatability, preserved key/database contents, and rejecting symbolic/hard links before mutations. Ownership operations are mocked in safe temporary-directory tests; no host permission changes or production installer execution occurred. Gunicorn configuration accepted umask 0077 (decimal 63). Fresh-server installation and actual cross-container UID access remain deployment-phase checks.
