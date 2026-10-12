"""خواندن امن XLSX، پیش‌نمایش قابل بازبینی و ورود/خروجی دارای هویت پایدار.

preview فقط snapshot و نتایج اعتبارسنجی را ذخیره می‌کند؛ inventory در apply تغییر می‌کند.
کل apply تراکنشی است و تصمیم تطبیق، تعارض و حذف دیسک باید صریح باشد.
فایل اصلی و رمز احتمالی ورودی رمزگذاری می‌شوند؛ API پیش‌نمایش مقدار رمز را حذف می‌کند.
"""

import io, json, re, uuid, zipfile
from xml.etree.ElementTree import ParseError
from defusedxml.common import DefusedXmlException
from openpyxl.utils.exceptions import InvalidFileException
from copy import copy
from decimal import Decimal
from pathlib import Path
from cryptography.fernet import Fernet
from django.conf import settings
from django.db import transaction
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from rest_framework.exceptions import ValidationError
from .models import (
    Machine,
    Environment,
    ImportBatch,
    Credential,
    Activity,
    ImportValidation,
    ImportDecision,
)
from .inventory import snapshot, save_machine
from .security import encrypt, decrypt, require, audit
from .validation import capacity, network_fields

LABELS = {
    "Row": "row",
    "Environment": "environment",
    "Application": "application",
    "VMs": "vms",
    "CPU (Core)": "cpu",
    "RAM (GB)": "ram",
    "OS": "os",
    "Network": "network",
    "Network / VLAN": "network",
    "Server Name": "server_name",
    "Server IP Addr": "ip",
    "Subnet (CIDR)": "subnet",
    "GW IP Addr": "gateway",
    "Username": "username",
    "Password": "password",
    "Machine UUID": "uuid",
    "Disk metadata": "disk_metadata",
    "Workflow status": "status",
}
VALID_FIELDS = set(LABELS.values()) | {"disk", "ignore"}
MAX_ROWS = 10000


def load_safe(raw):
    """حدود فایل/ZIP و محتوای ممنوع را پیش از parsing کنترل می‌کند؛ فرمول اجرا نمی‌شود."""
    if len(raw) > settings.DATA_UPLOAD_MAX_MEMORY_SIZE:
        raise ValidationError("فایل بیش از حد مجاز است")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if (
                sum(i.file_size for i in z.infolist()) > 80 * 1024 * 1024
                or len(z.infolist()) > 1000
            ):
                raise ValidationError("فایل فشرده بیش از حد مجاز است")
            if any(
                "vbaProject" in i.filename or "externalLinks/" in i.filename
                for i in z.infolist()
            ):
                raise ValidationError("ماکرو و پیوند خارجی مجاز نیست")
        wb = load_workbook(io.BytesIO(raw), data_only=False, keep_links=False)
        if any(s.max_row > MAX_ROWS + 100 or s.max_column > 150 for s in wb):
            raise ValidationError("ابعاد فایل بیش از حد مجاز است")
        return wb
    except (
        zipfile.BadZipFile,
        KeyError,
        ValueError,
        OSError,
        ParseError,
        DefusedXmlException,
        InvalidFileException,
    ):
        raise ValidationError("فایل XLSX معتبر نیست")


def encrypt_file(raw):
    return Fernet(settings.CREDENTIAL_KEY.encode()).encrypt(raw)


def batch_workbook(batch):
    with batch.file.open("rb") as f:
        raw = Fernet(settings.CREDENTIAL_KEY.encode()).decrypt(f.read())
    return load_safe(raw)


def detect(ws):
    best = (0, 1, {})
    for row in ws.iter_rows(min_row=1, max_row=min(30, ws.max_row)):
        mapping = {}
        for c in row:
            label = str(c.value or "").strip()
            if label in LABELS:
                mapping[str(c.column)] = LABELS[label]
            elif re.match(
                r"^(?:HDD(?: \d+)?(?: \(GB\))?|Disk \d+(?: \(GB\))?)$", label, re.I
            ):
                mapping[str(c.column)] = "disk"
        if len(mapping) > best[0]:
            best = (len(mapping), row[0].row, mapping)
    return {
        "header_row": best[1],
        "mapping": best[2],
        "headers": [
            str(ws.cell(best[1], i).value or "") for i in range(1, ws.max_column + 1)
        ],
    }


def inspect(batch):
    wb = batch_workbook(batch)
    return [{"name": s.title, **detect(s)} for s in wb]


def public_preview(batch):
    """نسخه قابل ارسال به مرورگر؛ ciphertext رمز نیز از این پاسخ حذف می‌شود."""
    rows = []
    for row in batch.preview:
        r = {k: v for k, v in row.items() if k != "secret"}
        r["credential_present"] = bool(row.get("secret"))
        rows.append(r)
    return rows


def preview(batch, worksheet, mapping, header_row, mode):
    """نگاشت ستون، merged ranges و snapshot نامزدها را ثبت می‌کند؛ ماشین نمی‌سازد."""
    if batch.status == "applied":
        raise ValidationError("این ورود قبلاً اعمال شده است")
    if mode not in ["add_only", "add_update"]:
        raise ValidationError("حالت نامعتبر")
    wb = batch_workbook(batch)
    if worksheet not in wb.sheetnames:
        raise ValidationError("Worksheet نامعتبر")
    if not isinstance(mapping, dict) or not 1 <= int(header_row) <= 30:
        raise ValidationError("نگاشت نامعتبر")
    for c, f in mapping.items():
        if not str(c).isdigit() or not 1 <= int(c) <= 150 or f not in VALID_FIELDS:
            raise ValidationError("نگاشت نامعتبر")
    singles = [f for f in mapping.values() if f not in ["disk", "ignore"]]
    if len(set(singles)) != len(singles) or not {"environment", "server_name"}.issubset(
        singles
    ):
        raise ValidationError("ستون‌های محیط و نام سرور باید یک‌بار نگاشت شوند")
    ws = wb[worksheet]
    merged = {}
    for area in ws.merged_cells.ranges:
        field = mapping.get(str(area.min_col))
        if field in ["environment", "application"]:
            for r in range(area.min_row, area.max_row + 1):
                merged[(r, area.min_col)] = ws.cell(area.min_row, area.min_col).value
    rows = []
    issues = []
    seen = set()
    ips = set()
    for r in range(int(header_row) + 1, ws.max_row + 1):
        values = {}
        disks = []
        errors = []
        for c, f in sorted(mapping.items(), key=lambda x: int(x[0])):
            if f == "ignore":
                continue
            cell = ws.cell(r, int(c))
            v = merged.get((r, int(c)), cell.value)
            # Export escapes text beginning with formula markers. UUID-bearing round trips decode that text only.
            if (
                wb.properties.identifier == "InfraHub-escaped-text-v1"
                and isinstance(v, str)
                and v.startswith("'")
            ):
                v = v[1:]
            if cell.data_type == "f":
                errors.append("فرمول در ورودی مجاز نیست")
                v = None
            if f == "disk":
                try:
                    size = capacity(v)
                    if Decimal(size) > 0:
                        disks.append(
                            {
                                "name": f"Disk {len(disks) + 1}",
                                "size": size,
                                "order": len(disks),
                            }
                        )
                except ValidationError:
                    errors.append("ظرفیت دیسک نامعتبر")
            else:
                values[f] = str(v or "").strip()
        if not values.get("server_name") and not any(
            values.get(k)
            for k in ["vms", "ip", "cpu", "ram", "os", "username", "password"]
        ):
            continue
        for k in ["row", "disk_metadata"]:
            values.pop(k, None)
        credential = values.pop("password", "")
        ident = values.pop("uuid", "")
        try:
            if not values.get("server_name") or not values.get("environment"):
                raise ValidationError("نام سرور و محیط الزامی است")
            values["cpu"] = capacity(values.get("cpu"), True)
            values["ram"] = capacity(values.get("ram"))
            warnings = network_fields(values)
            context = (
                values.get("environment"),
                values.get("network", ""),
                values.get("ip"),
            )
            if values.get("ip"):
                if (
                    context in ips
                    or Machine.objects.filter(
                        project=batch.project,
                        environment__name=values.get("environment"),
                        network=values.get("network", ""),
                        ip=values["ip"],
                        archived=False,
                    ).exists()
                ):
                    warnings.append("IP تکراری در همین پروژه، محیط و شبکه")
                ips.add(context)
            if values.get("os") and not any(
                v in values["os"].lower()
                for v in [
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
            if len(disks) > 64:
                raise ValidationError("حداکثر ۶۴ دیسک مجاز است")
            for k in [
                "server_name",
                "environment",
                "application",
                "os",
                "network",
                "username",
                "vms",
            ]:
                if len(values.get(k, "")) > (
                    120 if k == "environment" else 240 if k == "vms" else 180
                ):
                    raise ValidationError("مقدار متنی بیش از حد طولانی است")
            if values.get("status", "planned") not in [
                "planned",
                "in_progress",
                "completed",
                "blocked",
            ]:
                raise ValidationError("وضعیت نامعتبر")
        except ValidationError as e:
            errors.append(str(e.detail))
            warnings = []
        current = None
        candidates = []
        if ident:
            try:
                ident = str(uuid.UUID(ident))
                if ident in seen:
                    errors.append("شناسه ماشین در فایل تکرار شده است")
                seen.add(ident)
                current = Machine.objects.filter(
                    project=batch.project, id=ident
                ).first()
                if not current:
                    errors.append("شناسه UUID در پروژه یافت نشد")
            except ValueError:
                errors.append("UUID نامعتبر")
        else:
            candidates = list(
                Machine.objects.filter(
                    project=batch.project,
                    server_name=values.get("server_name", ""),
                    environment__name=values.get("environment", ""),
                )
                .select_related("environment", "application")
                .prefetch_related("disks")
            )
        # Hidden disk metadata preserves stable IDs/names across a round trip.
        meta_col = next(
            (int(c) for c, f in mapping.items() if f == "disk_metadata"), None
        )
        if meta_col and ws.cell(r, meta_col).value:
            try:
                meta = json.loads(ws.cell(r, meta_col).value)
                if len(meta) != len(disks):
                    raise ValueError()
                for d, m in zip(disks, meta):
                    d["id"] = str(uuid.UUID(m["id"]))
                    d["name"] = str(m["name"])
                    d["order"] = int(m["order"])
            except (ValueError, KeyError, TypeError):
                errors.append("متادیتای دیسک نامعتبر")
        if len(credential) > 4096:
            errors.append("Password بیش از حد مجاز است")
        meta_ids = [d["id"] for d in disks if d.get("id")]
        if (
            len(meta_ids) != len(set(meta_ids))
            or len({d["order"] for d in disks}) != len(disks)
            or any(not 0 <= d["order"] < 10000 or len(d["name"]) > 120 for d in disks)
        ):
            errors.append("شناسه، نام یا ترتیب دیسک نامعتبر")
        values["disks"] = disks
        rows.append(
            {
                "row": r,
                "data": values,
                "match": str(current.id) if current else None,
                "current": snapshot(current) if current else None,
                "candidates": [snapshot(m) for m in candidates],
                "warnings": warnings,
                "errors": errors,
                "secret": encrypt(credential) if credential else "",
            }
        )
        if errors:
            issues.append({"row": r, "errors": errors})
    if not rows:
        issues.append({"row": None, "errors": ["هیچ ماشین قابل ورود یافت نشد"]})
    batch.worksheet = worksheet
    batch.mappings = {"columns": mapping, "header_row": int(header_row)}
    batch.mode = mode
    batch.preview = rows
    batch.issues = issues
    batch.status = "preview"
    batch.version += 1
    batch.save()
    results = []
    for issue in issues:
        results.extend(
            ImportValidation(
                batch=batch,
                preview_version=batch.version,
                row=issue["row"],
                severity="error",
                message=message,
            )
            for message in issue["errors"]
        )
    for row in rows:
        results.extend(
            ImportValidation(
                batch=batch,
                preview_version=batch.version,
                row=row["row"],
                severity="warning",
                message=message,
            )
            for message in row["warnings"]
        )
    ImportValidation.objects.bulk_create(results)
    return public_preview(batch)


@transaction.atomic
def apply(batch, user, decisions, version):
    """تمام تصمیم‌های یک preview معتبر را با rollback کامل در صورت خطا اعمال می‌کند.

    snapshot و نسخه هدف از سرور گرفته می‌شوند؛ caller نمی‌تواند نسخه مبنا را جعل کند.
    نام/IP شناسه خودکار نیست؛ workbook بدون UUID نیازمند تصمیم صریح تطبیق است.
    """
    from .api import Conflict

    batch = ImportBatch.objects.select_for_update().get(id=batch.id)
    if batch.version != version or batch.status != "preview":
        raise Conflict("پیش‌نمایش منقضی یا قبلاً اعمال شده است")
    if batch.issues:
        raise ValidationError("خطاهای اعتبارسنجی باید اصلاح شوند")
    if not isinstance(decisions, dict):
        raise ValidationError("تصمیم‌ها نامعتبر است")
    counts = {"added": 0, "updated": 0, "skipped": 0}
    touched = set()
    # Lock the project to serialize imports, including creation of environments.
    type(batch.project).objects.select_for_update().get(id=batch.project_id)
    for row in batch.preview:
        decision = decisions.get(str(row["row"]))
        if not isinstance(decision, dict) or decision.get("action") not in [
            "apply",
            "skip",
        ]:
            raise ValidationError("تصمیم صریح برای هر ردیف الزامی است")
        if set(decision) - {"action", "match", "fields", "disks", "credential"}:
            raise ValidationError("فیلد تصمیم ناشناخته است")
        if isinstance(decision.get("fields"), dict) and (
            set(decision["fields"]) - (set(row["data"]) - {"disks"})
            or any(v not in ["excel", "web"] for v in decision["fields"].values())
        ):
            raise ValidationError("تصمیم فیلد نامعتبر است")
        if decision.get("credential", "preserve") not in ["preserve", "apply"]:
            raise ValidationError("تصمیم اعتبارنامه نامعتبر است")
        if decision["action"] == "skip":
            counts["skipped"] += 1
            ImportDecision.objects.create(
                batch=batch,
                preview_version=batch.version,
                row=row["row"],
                user=user,
                action="skip",
            )
            continue
        candidate = row["current"]
        if row["candidates"]:
            match = decision.get("match")
            candidate = next((m for m in row["candidates"] if m["id"] == match), None)
            if match != "new" and not candidate:
                raise ValidationError("تطبیق صریح نام سرور الزامی است؛ IP شناسه نیست")
        machine = None
        if candidate:
            if batch.mode == "add_only":
                raise ValidationError("در حالت فقط افزودن، رکورد موجود باید رد شود")
            machine = (
                Machine.objects.select_for_update()
                .filter(id=candidate["id"], project=batch.project)
                .first()
            )
            if not machine or machine.version != candidate["version"]:
                raise Conflict("ماشین پس از پیش‌نمایش تغییر کرده است")
            if str(machine.id) in touched:
                raise ValidationError("یک ماشین بیش از یک‌بار هدف قرار گرفته است")
            touched.add(str(machine.id))
        data = dict(row["data"])
        env_name = data.pop("environment")
        env = Environment.objects.get_or_create(project=batch.project, name=env_name)[0]
        data["environment"] = env.id
        if machine:
            policy = decision.get("fields")
            if policy not in ["excel", "web"] and not isinstance(policy, dict):
                raise ValidationError("تصمیم تعارض فیلدها الزامی است")
            old = snapshot(machine)
            for k in list(data):
                if k == "disks":
                    continue
                choice = policy.get(k) if isinstance(policy, dict) else policy
                if choice not in ["excel", "web"]:
                    raise ValidationError("تصمیم همه فیلدها الزامی است")
                if choice == "web":
                    data[k] = old[k]
            disk_policy = decision.get("disks")
            if disk_policy not in ["replace", "preserve", "merge"]:
                raise ValidationError("تصمیم صریح حذف/حفظ دیسک‌ها الزامی است")
            if disk_policy == "preserve":
                data.pop("disks")
            else:
                incoming = data["disks"]
                existing = old["disks"]
                for i, d in enumerate(incoming):
                    if not d.get("id") and i < len(existing):
                        d["id"] = existing[i]["id"]
                        d["name"] = existing[i]["name"]
                if disk_policy == "merge":
                    incoming_ids = {d.get("id") for d in incoming}
                    for d in existing:
                        if d["id"] not in incoming_ids:
                            incoming.append(d)
                    for i, d in enumerate(incoming):
                        d["order"] = i
            data["version"] = machine.version
        machine, _ = save_machine(user, batch.project, data, machine, "excel")
        if row["secret"] and decision.get("credential") == "apply":
            require(user, batch.project, "manager", "credential_edit")
            Credential.objects.update_or_create(
                machine=machine,
                defaults={"ciphertext": row["secret"], "secret_reference": ""},
            )
            Activity.objects.create(
                machine=machine,
                author=user,
                event="credential_changed",
                source="excel",
                comment="[REDACTED]",
            )
            audit(user, "credential_edit", machine.id, source="excel")
        ImportDecision.objects.create(
            batch=batch,
            preview_version=batch.version,
            row=row["row"],
            user=user,
            machine=machine,
            action="apply",
            fields=decision.get("fields", "excel"),
            disks=decision.get("disks", "replace"),
            credential=decision.get("credential", "preserve"),
        )
        counts["updated" if candidate else "added"] += 1
    batch.status = "applied"
    batch.counts = counts
    batch.decisions = decisions
    batch.version += 1
    for row in batch.preview:
        row["secret"] = ""
    batch.save()
    audit(user, "import_applied", batch.id, counts=counts)
    return counts


def safe_cell(value):
    if isinstance(value, str) and (
        value.startswith("'")
        or value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
    ):
        return "'" + value
    return value


def export_inventory(project, environment=None, credentials=False, merged=True):
    """خروجی از داده جاری؛ UUID و هویت دیسک مخفی‌اند و رمز فقط پس از مجوز caller صادر می‌شود."""
    q = (
        Machine.objects.filter(project=project, archived=False)
        .select_related("environment", "application")
        .prefetch_related("disks")
        .order_by("environment__name", "application__name", "server_name", "id")
    )
    if environment:
        q = q.filter(environment_id=environment)
    machines = list(q)
    n = max([len(m.disks.all()) for m in machines] + [2])
    labels = (
        ["Row", "Environment", "Application", "VMs", "CPU (Core)", "RAM (GB)"]
        + ["HDD (GB)"] * n
        + [
            "OS",
            "Network",
            "",
            "Server Name",
            "Server IP Addr",
            "Subnet (CIDR)",
            "GW IP Addr",
            "Username",
            "Password",
            "Workflow status",
            "Machine UUID",
            "Disk metadata",
        ]
    )
    wb = Workbook()
    ws = wb.active
    ws.title = "Inventory"
    original = (
        ImportBatch.objects.filter(project=project, status="applied")
        .order_by("-created_at")
        .first()
    )
    header = 1
    mapping = None
    if original:
        wb = batch_workbook(original)
        ws = wb[original.worksheet]
        for s in list(wb):
            if s != ws:
                wb.remove(s)
        header = original.mappings["header_row"]
        mapping = {int(c): f for c, f in original.mappings["columns"].items()}
        for area in list(ws.merged_cells.ranges):
            ws.unmerge_cells(str(area))
        ws.delete_rows(header + 1, ws.max_row)
        # Original labels/order/widths are kept. Add missing extension columns.
        if "subnet" not in mapping.values() and "ip" in mapping.values():
            at = next(c for c, f in mapping.items() if f == "ip") + 1
            ws.insert_cols(at)
            mapping = {c + 1 if c >= at else c: f for c, f in mapping.items()}
            mapping[at] = "subnet"
            ws.cell(header, at, "Subnet (CIDR)")
        disks = [c for c, f in mapping.items() if f == "disk"]
        for _ in range(max(0, n - len(disks))):
            c = max(mapping) + 1
            mapping[c] = "disk"
            ws.cell(header, c, "HDD (GB)")
        for label, f in LABELS.items():
            if (
                f
                in [
                    "row",
                    "environment",
                    "application",
                    "vms",
                    "cpu",
                    "ram",
                    "os",
                    "network",
                    "server_name",
                    "ip",
                    "subnet",
                    "gateway",
                    "username",
                    "password",
                    "status",
                    "uuid",
                    "disk_metadata",
                ]
                and f not in mapping.values()
            ):
                c = max(mapping) + 1
                mapping[c] = f
                ws.cell(header, c, label)
    else:
        ws.append(labels)
        mapping = {
            i + 1: ("disk" if l == "HDD (GB)" else LABELS.get(l, "ignore"))
            for i, l in enumerate(labels)
        }
    env_start = app_start = header + 1
    previous_env = previous_app = None
    index = 0

    def merge_group(start, end, field):
        cols = [c for c, f in mapping.items() if f == field]
        if merged and cols and end > start:
            ws.merge_cells(
                start_row=start, end_row=end, start_column=cols[0], end_column=cols[0]
            )

    for m in machines:
        if previous_env is not None and m.environment_id != previous_env:
            merge_group(env_start, ws.max_row, "environment")
            merge_group(app_start, ws.max_row, "application")
            ws.append([None])
            env_start = app_start = ws.max_row + 1
        elif previous_app is not None and m.application_id != previous_app:
            merge_group(app_start, ws.max_row, "application")
            app_start = ws.max_row + 1
        index += 1
        row = ws.max_row + 1
        s = snapshot(m)
        disks = s["disks"]
        disk_i = 0
        values = {
            **s,
            "row": index,
            "environment": m.environment.name,
            "uuid": str(m.id),
            "password": decrypt(m.credential.ciphertext)
            if credentials and hasattr(m, "credential") and m.credential.ciphertext
            else "",
            "disk_metadata": json.dumps(disks),
        }
        for c, f in sorted(mapping.items()):
            if f == "disk":
                value = float(disks[disk_i]["size"]) if disk_i < len(disks) else None
                disk_i += 1
            elif f == "ignore":
                value = None
            else:
                value = values.get(f, "")
            ws.cell(row, c, safe_cell(value))
        previous_env = m.environment_id
        previous_app = m.application_id
    merge_group(env_start, ws.max_row, "environment")
    merge_group(app_start, ws.max_row, "application")
    for c, f in mapping.items():
        if f in ["uuid", "disk_metadata"]:
            ws.column_dimensions[get_column_letter(c)].hidden = True
        elif not original:
            ws.column_dimensions[get_column_letter(c)].width = (
                23 if f in ["server_name", "ip", "gateway"] else 18
            )
    for row in ws.iter_rows(min_row=header):
        for cell in row:
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = Border(*([Side(style="thin", color="CBD5E1")] * 4))
            if cell.row == header:
                cell.fill = PatternFill("solid", fgColor="12364A")
                cell.font = Font(color="FFFFFF", bold=True)
    ws.sheet_view.rightToLeft = True
    ws.freeze_panes = f"D{header + 1}"
    ws.auto_filter.ref = ws.dimensions
    wb.properties.identifier = "InfraHub-escaped-text-v1"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def export_activity(project, environment=None):
    wb = Workbook()
    ws = wb.active
    ws.title = "Activity"
    ws.append(
        [
            "Machine UUID",
            "Server Name",
            "Author",
            "Timestamp",
            "Event type",
            "Comment",
            "Field changes",
        ]
    )
    q = (
        Activity.objects.filter(machine__project=project)
        .select_related("machine", "author")
        .prefetch_related("changes")
        .order_by("created_at")
    )
    if environment:
        q = q.filter(machine__environment_id=environment)
    for a in q:
        ws.append(
            [
                safe_cell(v)
                for v in [
                    str(a.machine_id),
                    a.machine.server_name,
                    a.author.username,
                    a.created_at.isoformat(),
                    a.event,
                    a.comment,
                    json.dumps(
                        list(a.changes.values("field", "previous", "value")),
                        ensure_ascii=False,
                    ),
                ]
            ]
        )
    wb.properties.identifier = "InfraHub-escaped-text-v1"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
