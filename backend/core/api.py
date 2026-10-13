"""مرز HTTP برنامه: احراز هویت، CSRF، مجوز پروژه‌ای و تبدیل خطا به پاسخ امن.

پیش از فراخوانی سرویس‌ها، پروژه/ماشین از queryset محدود به کاربر انتخاب می‌شود.
بازیابی اعتبارنامه مسیر مستقلی دارد؛ پاسخ معمولی موجودی هرگز رمز را شامل نمی‌شود.
"""

import hashlib, io, json, uuid
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.db import transaction, IntegrityError
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import APIException, ValidationError, PermissionDenied
from rest_framework.views import exception_handler as drf_handler
from .models import *
from .security import (
    require,
    global_require,
    scope,
    audit,
    encrypt,
    decrypt,
    PROJECT_PERMISSIONS,
    GLOBAL_PERMISSIONS,
)
from .inventory import snapshot, save_machine, overview
from . import xlsx


class Conflict(APIException):
    status_code = 409
    default_detail = "تعارض نسخه"
    default_code = "conflict"


def exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        exc = ValidationError(exc.messages)
    if isinstance(exc, IntegrityError):
        exc = ValidationError("مقدار تکراری یا محدودیت پایگاه داده")
    if isinstance(exc, (ValueError, TypeError, KeyError, OverflowError)):
        exc = ValidationError("ساختار یا مقدار درخواست نامعتبر است")
    return drf_handler(exc, context)


def profile(user):
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "is_admin": user.is_superuser,
        "permissions": user.independent_permissions,
    }


def project_for(user, pk, role="viewer", permission=None):
    p = get_object_or_404(scope(user), pk=pk)
    require(user, p, role, permission)
    return p


def machine_for(user, pk, role="viewer", permission=None):
    m = get_object_or_404(
        Machine.objects.select_related(
            "project", "environment", "application"
        ).prefetch_related("disks"),
        pk=pk,
        project__in=scope(user),
    )
    require(user, m.project, role, permission)
    return m


def project_data(p, user):
    m = Membership.objects.filter(project=p, user=user).first()
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "vcenter_path": p.vcenter_path,
        "archived": p.archived,
        "version": p.version,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
        "created_by": p.created_by.username,
        "role": "manager" if user.is_superuser else m.role,
        "permissions": list(PROJECT_PERMISSIONS)
        if user.is_superuser
        else list(set(m.permissions + user.independent_permissions)),
        "environments": list(
            p.environments.values("id", "name", "archived", "version")
        ),
    }


@ensure_csrf_cookie
@require_http_methods(["GET"])
def session(request):
    return JsonResponse(
        {
            "user": profile(request.user) if request.user.is_authenticated else None,
            "sso": False,
            "mfa": "future_integration",
        }
    )


@csrf_protect
@require_http_methods(["POST"])
def login_view(request):
    try:
        data = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({"detail": "درخواست نامعتبر"}, status=400)
    username = str(data.get("username", ""))[:150]
    # Username key prevents bypass by changing proxy/IP headers. Reverse proxy also limits requests.
    key = hashlib.sha256(username.casefold().encode()).hexdigest()
    with transaction.atomic():
        attempt, _ = LoginAttempt.objects.get_or_create(
            key=key, defaults={"expires_at": timezone.now() + timedelta(minutes=15)}
        )
        attempt = LoginAttempt.objects.select_for_update().get(pk=attempt.pk)
        if attempt.expires_at < timezone.now():
            attempt.failures = 0
            attempt.expires_at = timezone.now() + timedelta(minutes=15)
        if attempt.failures >= 5:
            return JsonResponse(
                {"detail": "تلاش‌های زیاد؛ ۱۵ دقیقه بعد تلاش کنید"}, status=429
            )
        user = authenticate(
            request, username=username, password=data.get("password", "")
        )
        if not user:
            attempt.failures += 1
            attempt.save()
            return JsonResponse({"detail": "نام کاربری یا رمز نادرست است"}, status=401)
        attempt.delete()
    login(request, user)
    policy = SystemSetting.objects.filter(key="session_seconds").first()
    request.session.set_expiry(
        int(policy.value) if policy else settings.SESSION_COOKIE_AGE
    )
    audit(user, "login")
    return JsonResponse({"user": profile(user)})


@api_view(["POST"])
def logout_view(request):
    audit(request.user, "logout")
    logout(request)
    return Response({"ok": True})


@api_view(["POST"])
def password_change(request):
    if not request.user.check_password(request.data.get("old_password", "")):
        raise ValidationError("رمز فعلی نادرست است")
    password = request.data.get("new_password", "")
    validate_password(password, request.user)
    request.user.set_password(password)
    request.user.save()
    update_session_auth_hash(request, request.user)
    audit(request.user, "account_password_changed")
    return Response({"ok": True})


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    from django.db import connection

    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
            c.fetchone()
        return Response({"status": "ok"})
    except Exception:
        return Response({"status": "database_unavailable"}, status=503)


@api_view(["GET", "POST"])
def projects(request):
    if request.method == "GET":
        return Response(
            [
                project_data(p, request.user)
                for p in scope(request.user).select_related("created_by")
            ]
        )
    if not request.user.is_superuser:
        raise PermissionDenied("ایجاد پروژه نیازمند مدیر سیستم است")
    name = str(request.data.get("name", "")).strip()
    if not name or len(name) > 180:
        raise ValidationError("نام پروژه معتبر لازم است")
    p = Project.objects.create(
        name=name,
        description=str(request.data.get("description", "")),
        vcenter_path=str(request.data.get("vcenter_path", ""))[:500],
        created_by=request.user,
    )
    audit(request.user, "project_created", p.id)
    return Response(project_data(p, request.user), status=201)


@api_view(["PATCH"])
@transaction.atomic
def project_detail(request, pk):
    p = project_for(request.user, pk, "manager")
    p = Project.objects.select_for_update().get(pk=p.pk)
    if request.data.get("version") != p.version:
        raise Conflict()
    for k in ["name", "description", "vcenter_path", "archived"]:
        if k in request.data:
            setattr(p, k, request.data[k])
    if (
        not p.name.strip()
        or len(p.name) > 180
        or len(p.vcenter_path) > 500
        or not isinstance(p.archived, bool)
    ):
        raise ValidationError("مقدار پروژه نامعتبر")
    p.version += 1
    p.save()
    audit(request.user, "project_updated", p.id, name=p.name, archived=p.archived)
    return Response(project_data(p, request.user))


@api_view(["POST", "PATCH"])
@transaction.atomic
def environments(request, pk):
    p = project_for(request.user, pk, "manager")
    name = str(request.data.get("name", "")).strip()
    if not name or len(name) > 120:
        raise ValidationError("نام محیط نامعتبر")
    if request.method == "POST":
        e = Environment.objects.create(project=p, name=name)
    else:
        e = get_object_or_404(
            Environment.objects.select_for_update(),
            project=p,
            id=request.data.get("id"),
        )
        if request.data.get("version") != e.version:
            raise Conflict()
        previous_name = e.name
        e.name = name
        e.archived = request.data.get("archived", e.archived)
        if not isinstance(e.archived, bool):
            raise ValidationError("مقدار بایگانی نامعتبر")
        e.version += 1
        e.save()
    audit(
        request.user,
        "environment_saved",
        e.id,
        name=e.name,
        previous=previous_name if request.method == "PATCH" else None,
    )
    return Response(
        {"id": e.id, "name": e.name, "archived": e.archived, "version": e.version}
    )


@api_view(["GET", "POST"])
def machines(request, pk):
    p = project_for(
        request.user, pk, "editor" if request.method == "POST" else "viewer"
    )
    if request.method == "POST":
        if p.archived:
            raise ValidationError("پروژه بایگانی شده است")
        m, warnings = save_machine(request.user, p, request.data)
        return Response({"machine": snapshot(m), "warnings": warnings}, status=201)
    q = (
        p.machines.filter(archived=False)
        .select_related("environment", "application")
        .prefetch_related("disks")
    )
    if request.query_params.get("environment"):
        q = q.filter(environment_id=request.query_params["environment"])
    if request.query_params.get("search"):
        q = q.filter(server_name__icontains=request.query_params["search"][:180])
    # Bounded pages protect large inventories; frontend follows pages.
    page = max(1, int(request.query_params.get("page", "1")))
    total = q.count()
    return Response(
        {
            "results": [
                snapshot(m)
                for m in q.order_by("server_name", "id")[(page - 1) * 100 : page * 100]
            ],
            "count": total,
            "page": page,
        }
    )


@api_view(["GET", "PATCH"])
def machine_detail(request, pk):
    m = machine_for(
        request.user, pk, "editor" if request.method == "PATCH" else "viewer"
    )
    if request.method == "GET":
        return Response(snapshot(m))
    if m.project.archived:
        raise ValidationError("پروژه بایگانی شده است")
    m, warnings = save_machine(request.user, m.project, request.data, m)
    return Response({"machine": snapshot(m), "warnings": warnings})


@api_view(["GET"])
def resources(request, pk):
    return Response(
        overview(project_for(request.user, pk), request.query_params.get("environment"))
    )


@api_view(["GET", "POST", "PATCH"])
@transaction.atomic
def activity(request, pk):
    m = machine_for(
        request.user, pk, "operator" if request.method != "GET" else "viewer"
    )
    if request.method == "POST":
        event = request.data.get("event", "comment")
        if event not in ["comment", "completed_work"]:
            raise ValidationError("نوع رویداد نامعتبر")
        comment = str(request.data.get("comment", "")).strip()
        if not comment or len(comment) > 10000:
            raise ValidationError("متن معتبر لازم است")
        Activity.objects.create(
            machine=m, author=request.user, event=event, comment=comment
        )
    elif request.method == "PATCH":
        a = get_object_or_404(
            Activity.objects.select_for_update(),
            machine=m,
            id=request.data.get("id"),
            event__in=["comment", "completed_work"],
        )
        manager = (
            request.user.is_superuser
            or Membership.objects.filter(
                project=m.project, user=request.user, role="manager"
            ).exists()
        )
        if a.author_id != request.user.id and not manager:
            raise PermissionDenied("فقط نویسنده یا مدیر پروژه")
        if a.version != request.data.get("version"):
            raise Conflict()
        text = str(request.data.get("comment", "")).strip()
        if not text or len(text) > 10000:
            raise ValidationError("متن معتبر لازم است")
        CommentRevision.objects.create(
            activity=a, author=request.user, previous=a.comment
        )
        a.comment = text
        a.version += 1
        a.save()
        audit(request.user, "comment_revised", a.id)
    return Response(
        [
            {
                "id": a.id,
                "version": a.version,
                "event": a.event,
                "source": a.source,
                "author": a.author.username,
                "author_id": a.author_id,
                "comment": a.comment,
                "timestamp": a.created_at,
                "changes": list(a.changes.values("field", "previous", "value")),
                "revisions": list(
                    a.revisions.values("author__username", "previous", "created_at")
                ),
            }
            for a in m.activities.select_related("author")
            .prefetch_related("changes", "revisions")
            .order_by("-created_at")
        ]
    )


@api_view(["POST", "PUT"])
@transaction.atomic
def credentials(request, pk):
    action = request.data.get("action", "reveal")
    permission = "credential_edit" if request.method == "PUT" else "credential_view"
    m = machine_for(request.user, pk, "viewer", permission)
    if request.method == "PUT":
        m = Machine.objects.select_for_update().get(id=m.id)
        if request.data.get("version") != m.version:
            raise Conflict()
        password = request.data.get("password", "")
        reference = request.data.get("secret_reference", "")
        if (
            not isinstance(password, str)
            or len(password) > 4096
            or not isinstance(reference, str)
            or len(reference) > 300
            or (password and reference)
        ):
            raise ValidationError("رمز یا مرجع معتبر لازم است")
        Credential.objects.update_or_create(
            machine=m,
            defaults={
                "ciphertext": encrypt(password) if password else "",
                "secret_reference": reference,
            },
        )
        m.version += 1
        m.save()
        Activity.objects.create(
            machine=m,
            author=request.user,
            event="credential_changed",
            comment="[REDACTED]",
        )
        audit(request.user, "credential_edit", m.id)
        return Response({"ok": True, "version": m.version})
    if action not in ["reveal", "copy"]:
        raise ValidationError("عمل نامعتبر")
    c = get_object_or_404(Credential, machine=m)
    if c.secret_reference:
        raise ValidationError(
            "این رکورد مرجع مخزن رمز است؛ بازیابی خارجی پیکربندی نشده است"
        )
    audit(request.user, "credential_" + action, m.id)
    response = Response({"password": decrypt(c.ciphertext) if c.ciphertext else ""})
    response["Cache-Control"] = "no-store"
    return response


@api_view(["GET", "POST"])
def imports(request, pk):
    p = project_for(request.user, pk, "manager")
    if request.method == "POST":
        if p.archived:
            raise ValidationError("پروژه بایگانی شده است")
        f = request.FILES.get("file")
        if (
            not f
            or not f.name.lower().endswith(".xlsx")
            or f.size > settings.DATA_UPLOAD_MAX_MEMORY_SIZE
        ):
            raise ValidationError("فقط XLSX در محدوده حجم مجاز")
        raw = f.read()
        xlsx.load_safe(raw)
        b = ImportBatch.objects.create(
            project=p, user=request.user, filename=Path(f.name).name[:255]
        )
        b.file.save(str(b.id) + ".encrypted", ContentFile(xlsx.encrypt_file(raw)))
        audit(request.user, "import_uploaded", b.id)
        return Response(
            {"id": b.id, "sheets": xlsx.inspect(b), "version": b.version}, status=201
        )
    return Response(
        list(
            ImportBatch.objects.filter(project=p)
            .order_by("-created_at")
            .values(
                "id",
                "filename",
                "worksheet",
                "mode",
                "counts",
                "status",
                "created_at",
                "issues",
                "version",
                "decisions",
            )
        )
    )


@api_view(["GET", "POST"])
def import_detail(request, pk):
    b = get_object_or_404(ImportBatch, pk=pk, project__in=scope(request.user))
    require(request.user, b.project, "manager")
    if request.method == "GET":
        return Response(
            {
                "id": b.id,
                "sheets": xlsx.inspect(b),
                "rows": xlsx.public_preview(b),
                "issues": b.issues,
                "version": b.version,
                "status": b.status,
            }
        )
    if b.project.archived:
        raise ValidationError("پروژه بایگانی شده است")
    if request.data.get("action") == "apply":
        return Response(
            xlsx.apply(
                b,
                request.user,
                request.data.get("decisions"),
                request.data.get("version"),
            )
        )
    with transaction.atomic():
        b = ImportBatch.objects.select_for_update().get(id=b.id)
        if request.data.get("version") != b.version:
            raise Conflict()
        rows = xlsx.preview(
            b,
            request.data.get("worksheet"),
            request.data.get("mapping"),
            request.data.get("header_row", 1),
            request.data.get("mode", "add_only"),
        )
        return Response(
            {"rows": rows, "issues": b.issues, "version": b.version, "status": b.status}
        )


@api_view(["POST"])
def exports(request, pk):
    p = project_for(request.user, pk)
    m = Membership.objects.filter(user=request.user, project=p).first()
    if not request.user.is_superuser and (
        not m
        or (
            m.role not in ["editor", "manager"]
            and "export" not in m.permissions
            and "export" not in request.user.independent_permissions
        )
    ):
        raise PermissionDenied("مجوز خروجی لازم است")
    creds = request.data.get("credentials") is True
    if creds:
        require(request.user, p, "viewer", "credential_export")
    env = request.data.get("environment")
    if env:
        get_object_or_404(Environment, id=env, project=p)
    kind = request.data.get("kind", "inventory")
    if kind not in ["inventory", "activity"]:
        raise ValidationError("نوع خروجی نامعتبر")
    raw = (
        xlsx.export_activity(p, env)
        if kind == "activity"
        else xlsx.export_inventory(p, env, creds, request.data.get("merged", True))
    )
    ExportRecord.objects.create(
        project=p, user=request.user, credentials=creds, kind=kind
    )
    audit(request.user, "credential_export" if creds else "export", p.id, kind=kind)
    r = HttpResponse(
        raw,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    r["Content-Disposition"] = 'attachment; filename="infrahub-' + kind + '.xlsx"'
    r["Cache-Control"] = "no-store"
    return r


@api_view(["GET", "POST", "PATCH"])
@transaction.atomic
def users(request):
    global_require(request.user, "manage_users")
    if request.method == "GET":
        return Response(
            [
                dict(profile(u), is_active=u.is_active)
                for u in User.objects.all().order_by("id")
            ]
        )
    SystemSetting.objects.get_or_create(key="admin_lock", defaults={"value": {}})
    SystemSetting.objects.select_for_update().get(key="admin_lock")
    if request.method == "POST":
        username = str(request.data.get("username", ""))
        password = request.data.get("password", "")
        u = User(username=username)
        u.full_clean(exclude=["password"])
        validate_password(password, u)
        u.set_password(password)
    else:
        u = get_object_or_404(
            User.objects.select_for_update(), id=request.data.get("id")
        )
    previous_admin = u.is_superuser and u.is_active
    for k in ["first_name", "is_active"]:
        if k in request.data:
            setattr(u, k, request.data[k])
    if "is_admin" in request.data:
        if not request.user.is_superuser:
            raise PermissionDenied("تغییر مدیر فقط برای مدیر سیستم")
        u.is_superuser = request.data["is_admin"]
        u.is_staff = u.is_superuser
    if "permissions" in request.data:
        perms = request.data["permissions"]
        if not isinstance(perms, list) or set(perms) - (
            PROJECT_PERMISSIONS | GLOBAL_PERMISSIONS
        ):
            raise ValidationError("مجوز نامعتبر")
        if not request.user.is_superuser and set(perms) - set(
            request.user.independent_permissions
        ):
            raise PermissionDenied("نمی‌توانید مجوز بالاتر واگذار کنید")
        u.independent_permissions = perms
    if not isinstance(u.is_active, bool) or not isinstance(u.is_superuser, bool):
        raise ValidationError("وضعیت نامعتبر")
    if (
        previous_admin
        and not (u.is_active and u.is_superuser)
        and not User.objects.filter(is_active=True, is_superuser=True)
        .exclude(id=u.id)
        .exists()
    ):
        raise ValidationError("آخرین مدیر فعال قابل حذف یا تنزل نیست")
    u.save()
    audit(request.user, "user_saved", u.id)
    return Response(profile(u))


@api_view(["GET", "POST"])
@transaction.atomic
def memberships(request, pk):
    p = project_for(request.user, pk, "manager")
    if request.method == "GET":
        return Response(
            list(
                Membership.objects.filter(project=p).values(
                    "id", "user_id", "user__username", "role", "permissions"
                )
            )
        )
    global_require(request.user, "manage_users")
    user = get_object_or_404(User, id=request.data.get("user"))
    role = request.data.get("role")
    perms = request.data.get("permissions", [])
    if (
        role not in ["viewer", "operator", "editor", "manager"]
        or not isinstance(perms, list)
        or set(perms) - PROJECT_PERMISSIONS
    ):
        raise ValidationError("نقش یا مجوز نامعتبر")
    if not request.user.is_superuser and set(perms) - set(
        request.user.independent_permissions
    ):
        raise PermissionDenied("واگذاری مجوز مستقل نیازمند همان مجوز است")
    if request.data.get("remove") is True:
        Membership.objects.filter(project=p, user=user).delete()
    else:
        Membership.objects.update_or_create(
            project=p, user=user, defaults={"role": role, "permissions": perms}
        )
    audit(request.user, "membership_saved", p.id, user_id=user.id)
    return Response({"ok": True})


@api_view(["GET"])
def audit_events(request):
    global_require(request.user, "audit_view")
    return Response(
        list(
            Audit.objects.order_by("-created_at")[:500].values(
                "id", "user__username", "event", "target", "metadata", "created_at"
            )
        )
    )


@api_view(["GET", "PATCH"])
def system_settings(request):
    global_require(request.user, "auth_settings")
    if request.method == "PATCH":
        seconds = int(request.data.get("session_seconds", 3600))
        if not 300 <= seconds <= 86400:
            raise ValidationError("جلسه باید بین ۵ دقیقه و ۲۴ ساعت باشد")
        SystemSetting.objects.update_or_create(
            key="session_seconds", defaults={"value": seconds}
        )
        audit(request.user, "auth_settings_changed")
    return Response(
        {
            "session_seconds": SystemSetting.objects.filter(key="session_seconds")
            .values_list("value", flat=True)
            .first()
            or settings.SESSION_COOKIE_AGE,
            "sso": "unconfigured",
            "mfa": "future_integration",
        }
    )


@api_view(["GET", "POST"])
def updates(request):
    from .updates import version, check_release, queue_update

    global_require(request.user, "perform_updates")
    if request.method == "POST":
        if request.data.get("action") == "check":
            return Response(check_release(request.user))
        if not settings.UPDATE_EXECUTION_ENABLED:
            raise ValidationError(
                "سرویس مستقل به‌روزرسانی فعال نشده است؛ راهنمای دستی را ببینید"
            )
        run = queue_update(request.user, request.data.get("version", ""))
        return Response({"id": run.id, "status": run.status}, status=202)
    cached = (
        SystemSetting.objects.filter(key="release_check")
        .values_list("value", flat=True)
        .first()
    )
    runs = list(UpdateRun.objects.order_by("-created_at")[:30].values())
    for run in runs:
        journal = settings.UPDATE_STATE / ("progress-" + str(run["id"]) + ".json")
        if journal.exists():
            try:
                run["progress"] = json.loads(journal.read_text())
            except (OSError, ValueError):
                pass
        upgrade = settings.UPDATE_STATE / ("upgrade-" + run["to_version"] + ".json")
        if upgrade.exists():
            try:
                run["backup_path"] = json.loads(upgrade.read_text()).get("backup", "")
            except (OSError, ValueError):
                pass
    return Response(
        {
            "installed": version(),
            "available": cached,
            "execution_enabled": settings.UPDATE_EXECUTION_ENABLED,
            "runs": runs,
        }
    )


@api_view(["GET"])
def management_reports(request):
    from .reports import management_report
    project_id = request.query_params.get("project")
    environment_id = request.query_params.get("environment")
    project = project_for(request.user, project_id) if project_id else None
    if environment_id and project is None:
        raise ValidationError("برای انتخاب محیط، پروژه را انتخاب کنید")
    environment = get_object_or_404(Environment, pk=environment_id, project=project) if environment_id else None
    response = Response(management_report(scope(request.user), project, environment, int(request.query_params.get("page", 1))))
    response["Cache-Control"] = "no-store"
    return response
