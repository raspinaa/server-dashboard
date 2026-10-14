"""سرویس مشترک ویرایش وب و ورود Excel.

اعتبارسنجی، ذخیره ماشین/دیسک و ثبت اختلاف‌ها در یک تراکنش انجام می‌شوند.
این ماژول به زیرساخت متصل نمی‌شود؛ اعداد صرفاً موجودی تخصیص‌یافته‌اند.
"""

from decimal import Decimal
import uuid
from django.db import transaction
from django.db.models import Sum
from rest_framework.exceptions import ValidationError
from .models import Machine, Disk, Application, Environment, Activity, Change
from .validation import capacity, network_fields, normalize_interfaces
from .security import audit

FIELDS = [
    "environment",
    "application",
    "server_name",
    "vms",
    "cpu",
    "ram",
    "os",
    "network",
    "ip",
    "subnet",
    "gateway",
    "interfaces",
    "username",
    "status",
    "archived",
]


def snapshot(m):
    """نمای معمولی/تاریخی ماشین؛ وجود اعتبارنامه را می‌گوید ولی مقدار آن را برنمی‌گرداند."""
    return {
        "id": str(m.id),
        "version": m.version,
        "project": m.project_id,
        "environment": m.environment_id,
        "environment_name": m.environment.name,
        "application": m.application.name if m.application else "",
        **{
            k: str(getattr(m, k))
            if isinstance(getattr(m, k), Decimal)
            else getattr(m, k)
            for k in FIELDS
            if k not in ["environment", "application"]
        },
        "interfaces": m.interfaces or ([{k: getattr(m, k) for k in ['ip', 'subnet', 'gateway', 'network']}] if m.ip else []),
        "disks": [
            {"id": str(d.id), "name": d.name, "size": str(d.size), "order": d.order}
            for d in m.disks.all()
        ],
        "has_credential": hasattr(m, "credential"),
        "updated_at": m.updated_at.isoformat(),
    }


def normalize(project, data, existing=None):
    """فیلدهای مجاز را اعتبارسنجی می‌کند و محیط/دیسک را به همان پروژه/ماشین محدود می‌کند."""
    allowed = set(FIELDS + ["disks", "version"])
    if set(data) - allowed:
        raise ValidationError("فیلد ناشناخته")
    out = dict(data)
    explicit_interfaces = 'interfaces' in data
    out.pop("version", None)
    if existing:
        old = snapshot(existing)
        for k in FIELDS:
            out.setdefault(k, old[k])
    for k in [
        "server_name",
        "vms",
        "os",
        "network",
        "ip",
        "subnet",
        "gateway",
        "username",
    ]:
        out[k] = str(out.get(k, "")).strip()
        if len(out[k]) > (240 if k == "vms" else 180):
            raise ValidationError({k: "مقدار بیش از حد طولانی است"})
    if not out["server_name"]:
        raise ValidationError({"server_name": "نام سرور الزامی است"})
    env = Environment.objects.filter(
        project=project, id=out.get("environment"), archived=False
    ).first()
    if not env:
        raise ValidationError({"environment": "محیط معتبر انتخاب کنید"})
    out["environment"] = env.id
    app = str(out.get("application", "")).strip()
    if len(app) > 180:
        raise ValidationError({"application": "نام طولانی است"})
    out["application"] = app
    out["cpu"] = capacity(out.get("cpu"), True)
    out["ram"] = capacity(out.get("ram"))
    out.setdefault("status", "planned")
    out.setdefault("archived", False)
    if out["status"] not in ["planned", "in_progress", "completed", "blocked"]:
        raise ValidationError({"status": "وضعیت نامعتبر"})
    if not isinstance(out["archived"], bool):
        raise ValidationError({"archived": "مقدار بولی لازم است"})
    if explicit_interfaces:
        out['interfaces'], warnings = normalize_interfaces(out['interfaces'])
        first = out['interfaces'][0] if out['interfaces'] else dict(ip='', subnet='', gateway='', network=out['network'])
        out.update(first)
    else:
        if 'ip' in data and '/' in str(data['ip']) and 'subnet' not in data:
            out['subnet'] = ''
        warnings = network_fields(out)
        additional = list(out.get('interfaces') or [])[1:]
        primary = {k: out[k] for k in ['ip', 'subnet', 'gateway', 'network']}
        out['interfaces'], extra_warnings = normalize_interfaces([primary, *additional])
        warnings.extend(extra_warnings)
    if (
        out["ip"]
        and Machine.objects.filter(
            project=project,
            environment=env,
            network=out["network"],
            ip=out["ip"],
            archived=False,
        )
        .exclude(id=existing.id if existing else None)
        .exists()
    ):
        warnings.append("IP تکراری در همین پروژه، محیط و شبکه")
    if out["os"] and not any(
        x in out["os"].lower()
        for x in [
            "ubuntu",
            "debian",
            "windows",
            "linux",
            "centos",
            "rocky",
            "red hat",
            "rhel",
            "oracle",
            "suse",
            "freebsd",
        ]
    ):
        warnings.append("برچسب OS نیازمند بررسی است؛ مقدار حفظ شد")
    if "disks" in out:
        if not isinstance(out["disks"], list) or len(out["disks"]) > 64:
            raise ValidationError({"disks": "حداکثر ۶۴ دیسک"})
        ids = set()
        orders = set()
        for i, d in enumerate(out["disks"]):
            d = dict(d)
            size = capacity(d.get("size"))
            if Decimal(size) <= 0:
                raise ValidationError({"disks": "ظرفیت دیسک باید مثبت باشد"})
            ident = str(d.get("id") or uuid.uuid4())
            try:
                uuid.UUID(ident)
            except ValueError:
                raise ValidationError({"disks": "شناسه دیسک نامعتبر"})
            order = int(d.get("order", i))
            name = str(d.get("name", f"Disk {i + 1}")).strip()
            if (
                ident in ids
                or order in orders
                or not 0 <= order < 10000
                or not name
                or len(name) > 120
            ):
                raise ValidationError({"disks": "نام، ترتیب یا شناسه دیسک نامعتبر"})
            if Disk.objects.filter(id=ident).exclude(machine=existing).exists():
                raise ValidationError({"disks": "شناسه متعلق به ماشین دیگری است"})
            ids.add(ident)
            orders.add(order)
            out["disks"][i] = {"id": ident, "name": name, "size": size, "order": order}
    return out, warnings


@transaction.atomic
def save_machine(user, project, data, machine=None, source="web"):
    """ذخیره اتمیک همراه تاریخچه؛ caller باید مجوز را پیش‌تر بررسی کرده باشد.

    row lock و expected version از overwrite ویرایش هم‌زمان جلوگیری می‌کنند.
    نبودن کلید disks یعنی حفظ دیسک‌ها؛ آرایه خالی، حذف صریح همه دیسک‌هاست.
    """
    if machine:
        machine = Machine.objects.select_for_update().get(id=machine.id)
        if data.get("version") != machine.version:
            from .api import Conflict

            raise Conflict("رکورد تغییر کرده است؛ دوباره بارگذاری کنید")
        before = snapshot(machine)
    else:
        before = None
    clean, warnings = normalize(project, data, machine)
    disks = clean.pop("disks", None)
    app = clean.pop("application")
    app_obj = (
        Application.objects.get_or_create(project=project, name=app)[0] if app else None
    )
    clean["application"] = app_obj
    clean["environment_id"] = clean.pop("environment")
    if machine:
        for k, v in clean.items():
            setattr(machine, k, v)
        machine.version += 1
        machine.save()
    else:
        machine = Machine.objects.create(project=project, created_by=user, **clean)
    if disks is not None:
        # Remove only through an explicit full disk edit or reviewed import decision.
        machine.disks.exclude(id__in=[d["id"] for d in disks]).delete()
        # Two-phase ordering avoids transient unique-key collisions on swaps.
        for d in machine.disks.all():
            d.order += 1000000
            d.save(update_fields=["order"])
        for d in disks:
            Disk.objects.update_or_create(
                id=d["id"],
                machine=machine,
                defaults={k: v for k, v in d.items() if k != "id"},
            )
    activity = Activity.objects.create(
        machine=machine,
        author=user,
        event="updated" if before else "created",
        source=source,
    )
    after = snapshot(machine)
    changed = []
    for k in FIELDS + ["disks"]:
        if not before or before[k] != after[k]:
            changed.append(k)
            Change.objects.create(
                activity=activity,
                field=k,
                previous=before[k] if before else None,
                value=after[k],
            )
    audit(user, 'machine_updated' if before else 'machine_created', machine.id,
          project=project.id, server_name=machine.server_name, source=source,
          activity=activity.id, fields=changed)
    return machine, warnings


def overview(project, env=None):
    """جمع منابع ثبت‌شده؛ کل پروژه و محیط انتخابی جدا هستند و مقدار مصرف زنده نداریم."""
    q = Machine.objects.filter(project=project, archived=False)
    if env:
        q = q.filter(environment_id=env)

    def totals(rows):
        ids = rows.values_list("id", flat=True)
        return {
            "machines": rows.count(),
            "cpu": rows.aggregate(x=Sum("cpu"))["x"] or 0,
            "ram": str(rows.aggregate(x=Sum("ram"))["x"] or 0),
            "disk": str(
                Disk.objects.filter(machine_id__in=ids).aggregate(x=Sum("size"))["x"]
                or 0
            ),
            "statuses": {
                s: rows.filter(status=s).count()
                for s in ["planned", "in_progress", "completed", "blocked"]
            },
        }

    return {
        "project": totals(Machine.objects.filter(project=project, archived=False)),
        "selected": totals(q),
        "environments": [
            {
                "id": e.id,
                "name": e.name,
                **totals(
                    Machine.objects.filter(
                        project=project, archived=False, environment=e
                    )
                ),
            }
            for e in project.environments.filter(archived=False)
        ],
    }
