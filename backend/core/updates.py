"""بررسی metadata انتشار و ثبت صف به‌روزرسانی؛ اجرای استقرار داخل HTTP نیست.

مخزن و کانال از تنظیمات مسئول استقرار می‌آیند، نه payload کاربر.
مجوز مستقل و قفل تراکنشی قبل از صف‌کردن بررسی می‌شوند؛ helper امضا را می‌سنجد.
"""

import base64, hashlib, json, os, re
from pathlib import Path
import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import SystemSetting, UpdateRun
from .security import audit, global_require

SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def version():
    return (Path(__file__).resolve().parents[2] / "VERSION").read_text().strip()


def valid_version(v):
    if not isinstance(v, str) or not SEMVER.fullmatch(v):
        raise ValidationError("انتشار باید نسخه پایدار SemVer باشد")
    return v


def release_metadata(v=None):
    repo = settings.RELEASE_REPOSITORY
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValidationError("مخزن انتشار توسط مسئول استقرار پیکربندی نشده است")
    if settings.RELEASE_CHANNEL != "stable":
        raise ValidationError("در این نسخه تنها کانال stable پشتیبانی می‌شود")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token_file = os.getenv("RELEASE_TOKEN_FILE")
    if token_file:
        headers["Authorization"] = "Bearer " + Path(token_file).read_text().strip()
    endpoint = f"https://api.github.com/repos/{repo}/releases/" + (
        "tags/v" + valid_version(v) if v else "latest"
    )
    try:
        r = requests.get(endpoint, headers=headers, timeout=20, allow_redirects=False)
        r.raise_for_status()
        data = r.json()
        if data.get("draft") or data.get("prerelease"):
            raise ValueError()
        ver = valid_version(data["tag_name"].removeprefix("v"))
        assets = {a["name"]: a["url"] for a in data.get("assets", [])}
        if not {
            "manifest.json",
            "manifest.sig",
            "infrahub-" + ver + ".tar.gz",
        }.issubset(assets):
            raise ValueError()
        return {
            "version": ver,
            "notes": data.get("body", "")[:30000],
            "assets": assets,
            "compatibility": {
                "python": "3.12",
                "mysql": "8.4 LTS",
                "os": "Ubuntu 24.04",
                "architectures": ["amd64"],
                "signature": "Ed25519 manifest required",
            },
            "checked_at": timezone.now().isoformat(),
        }
    except (requests.RequestException, ValueError, KeyError):
        raise ValidationError(
            "دریافت انتشار ممکن نیست؛ دسترسی GitHub و ساختار انتشار را بررسی کنید"
        )


def check_release(user):
    try:
        data = release_metadata()
        SystemSetting.objects.update_or_create(
            key="release_check", defaults={"value": data}
        )
        audit(user, "release_checked", data["version"])
        return data
    except ValidationError:
        audit(user, "release_check_failed")
        raise


@transaction.atomic
def queue_update(user, v):
    global_require(user, "perform_updates")
    valid_version(v)
    cached = SystemSetting.objects.filter(key="release_check").first()
    if not cached or cached.value.get("version") != v:
        raise ValidationError("ابتدا انتشار انتخاب‌شده را بررسی کنید")
    previous_failure = (
        UpdateRun.objects.filter(to_version=v, status="failed").exists()
        and (settings.UPDATE_STATE / "maintenance").exists()
    )
    if tuple(map(int, v.split("."))) <= tuple(map(int, version().split("."))) and not (
        v == version() and previous_failure
    ):
        raise ValidationError("نسخه مقصد باید جدیدتر یا ادامه اجرای ناموفق باشد")
    SystemSetting.objects.get_or_create(key="update_lock", defaults={"value": {}})
    SystemSetting.objects.select_for_update().get(key="update_lock")
    if UpdateRun.objects.filter(status__in=["queued", "running"]).exists():
        raise ValidationError("یک به‌روزرسانی در صف یا اجراست")
    run = UpdateRun.objects.create(user=user, from_version=version(), to_version=v)
    audit(user, "update_queued", run.id, version=v)
    return run
