# مدیریت آفلاین

پس از نصب بسته، فرمان‌های زیر با sudo قابل استفاده‌اند:

```bash
infrahub backup
infrahub backup --destination /srv/protected-backups
infrahub stage /srv/infrahub-new-package
infrahub update /srv/infrahub-new-package
infrahub update
infrahub restore /PATH/infrahub-backup-TIMESTAMP.tar.gz --confirm
```

`backup` پشتیبان کامل فشرده با تاریخ تهران از دیتابیس، فایل‌ها، کلیدها، سورس و تصاویر می‌گیرد. `stage` بسته محلی را اعتبارسنجی و برای dashboard معرفی می‌کند. `update` با مسیر از همان بسته و بدون مسیر از آخرین بسته محلی آماده‌شده استفاده می‌کند. هیچ اتصال به GitHub یا دانلود ندارد؛ `--commit` حذف شده است. `restore` پس از checksum و snapshot وضعیت فعلی، سورس/تصاویر/دیتابیس قبلی را بازمی‌گرداند؛ داده‌های فعلی بازنویسی می‌شوند و تأیید صریح لازم است.

[جزئیات بسته آفلاین، کلید امضا، قفل‌ها و محدودیت‌ها](offline.fa.md). نصب ابزار CLI فقط از wheel محلی با --no-index و hash انجام می‌شود. backup شامل کلید است و باید به فضای بیرونی محدود/رمزگذاری‌شده کپی شود. به‌روزرسانی واقعی میزبان در این تحویل اجرا نشده است.
