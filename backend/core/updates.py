"""بررسی metadata انتشار و ثبت صف به‌روزرسانی؛ اجرای استقرار داخل HTTP نیست.

مخزن و کانال از تنظیمات مسئول استقرار می‌آیند، نه payload کاربر.
مجوز مستقل و قفل تراکنشی قبل از صف‌کردن بررسی می‌شوند؛ helper امضا را می‌سنجد.
"""

import base64, hashlib, json, os, re
from pathlib import Path
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
    path = settings.UPDATE_STATE / "offline-release.json"
    try:
        data = json.loads(path.read_text())
        valid_version(data["version"])
        if v and data["version"] != valid_version(v):
            raise ValueError()
        return data
    except (OSError, ValueError, KeyError):
        raise ValidationError("بسته آفلاین آماده نشده است؛ مدیر روی سرور infrahub stage PACKAGE را اجرا کند")


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
