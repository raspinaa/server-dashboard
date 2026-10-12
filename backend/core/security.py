"""کنترل دسترسی و رمزگذاری اعتبارنامه‌ها.

نقش پروژه و مجوز مستقل دو شرط جدا هستند؛ مجوز مستقل عضویت پروژه نمی‌سازد.
مقادیر رمز فقط داخل مسیر بازیابی مجاز باز می‌شوند و وارد audit نمی‌شوند.
"""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import Membership, Project, Audit

RANK = {"viewer": 0, "operator": 1, "editor": 2, "manager": 3}
PROJECT_PERMISSIONS = {
    "export",
    "credential_view",
    "credential_edit",
    "credential_export",
}
GLOBAL_PERMISSIONS = {"manage_users", "auth_settings", "audit_view", "perform_updates"}


def scope(user):
    """Queryset مجاز؛ برای جلوگیری از افشای رکوردهای پروژه‌های دیگر قبل از lookup استفاده شود."""
    if user.is_superuser:
        return Project.objects.all()
    return Project.objects.filter(membership__user=user)


def require(user, project, role="viewer", permission=None):
    """پس از تعیین scope، حداقل نقش و در صورت نیاز مجوز مستقل را هم‌زمان اعمال می‌کند."""
    if user.is_active and user.is_superuser:
        return
    m = Membership.objects.filter(user=user, project=project).first()
    if not user.is_active or not m or RANK[m.role] < RANK[role]:
        raise PermissionDenied("دسترسی مجاز نیست")
    if (
        permission
        and permission not in m.permissions
        and permission not in user.independent_permissions
    ):
        raise PermissionDenied("مجوز مستقل لازم است")


def global_require(user, permission):
    if not user.is_active or not (
        user.is_superuser or permission in user.independent_permissions
    ):
        raise PermissionDenied("مجوز مدیر لازم است")


def encrypt(value):
    """رمزگذاری احرازشده با کلید خارج از دیتابیس؛ فقط ciphertext قابل ذخیره است."""
    try:
        return Fernet(settings.CREDENTIAL_KEY.encode()).encrypt(value.encode()).decode()
    except (ValueError, TypeError):
        raise ValidationError("کلید رمزگذاری پیکربندی نشده است")


def decrypt(value):
    try:
        return Fernet(settings.CREDENTIAL_KEY.encode()).decrypt(value.encode()).decode()
    except (ValueError, InvalidToken):
        raise ValidationError("بازیابی رمز ممکن نیست؛ پیکربندی کلید را بررسی کنید")


def audit(user, event, target="", **metadata):
    """فقط شناسه و نتیجه عملیات دریافت کند؛ request.data یا مقدار credential را ندهید."""
    # Callers supply identifiers and outcomes only, never secret-bearing payloads.
    Audit.objects.create(user=user, event=event, target=str(target), metadata=metadata)
