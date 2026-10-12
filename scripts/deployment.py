"""ساخت یکسان فرمان Compose برای نصب اولیه، backup و helper به‌روزرسانی.

تنظیمات site بیرون سورس قابل‌جایگزینی deploy نگهداری می‌شوند؛ ارتقا نباید
انتخاب DNS، پورت یا حالت گواهی اپراتور را حذف کند.
"""
from pathlib import Path


def compose_command(root):
    root = Path(root).resolve()
    args = ["docker", "compose", "--env-file", str(root / ".env"), "-f", str(root / "deploy/compose.prod.yml")]
    site = root / "config/compose.site.yml"
    if site.is_file():
        args += ["-f", str(site)]
    return args
