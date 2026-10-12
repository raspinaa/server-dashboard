# نسخه و انتشار آینده

`VERSION` تنها منبع نسخه برنامه است؛ package.json مقدار هماهنگ برای tooling دارد و CI تطابق آن را بررسی می‌کند. SemVer: patch برای fix، minor برای feature سازگار، major برای breaking change. این تحویل 0.1.0 Unreleased است و ثبت تغییرات سورس با commit انجام می‌شود؛ tag و release رسمی هنوز ساخته نشده‌اند.

پس از مجوز نشر آینده: تغییرات هر batch با commit قابل بازبینی، آزمون MySQL/UI، changelog، migration/backup guidance ثبت شود. نسخه VERSION و package manifest هماهنگ، tag `vX.Y.Z` روی commit تأییدشده، release notes مطابق template آماده شود. CI فعلی فقط check/build می‌کند؛ دسترسی نشر ندارد.

ساخت artifact محلی: `python scripts/release.py --output artifacts/X.Y.Z --signing-key /secure/ed25519-private.key`. کلید private ۳۲ بایت base64، کلید public ۳۲ بایت base64، امضا base64 است. key تولید و نگهداری خارج source و خارج host برنامه باشد. این دستور سورس و build frontend را بسته‌بندی می‌کند، منتشر نمی‌کند. بسته تنها شامل paths allowlisted است و local env/data/cache/keys وارد آن نمی‌شوند. در CI release future کلید از secret store با filesystem محدود وارد شود، manifest امضاشده و release notes منتشر شوند. digest تصاویر build و SBOM نیز در review انتشار ثبت شوند.

از repository URL ساختگی، tag جعلی یا checksum تغییر داده‌شده برای عبور verification استفاده نکنید. published release هنوز integration آینده است؛ دانلود خصوصی/نشر تصویر/استقرار این فاز انجام نشده‌اند.
