"""مدل‌های پایدار موجودی، دسترسی، تاریخچه و عملیات InfraHub.

روابط مهم PROTECT هستند تا حذف اتفاقی پروژه یا کاربر سابقه را از بین نبرد.
هویت ماشین و دیسک UUID است؛ نام سرور، IP و شماره ردیف Excel هویت نیستند.
"""

import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    independent_permissions = models.JSONField(default=list, blank=True)


class Project(models.Model):
    name = models.CharField(max_length=180, db_collation="utf8mb4_0900_as_cs")
    description = models.TextField(blank=True)
    vcenter_path = models.CharField(max_length=500, blank=True)
    archived = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="created_projects"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Membership(models.Model):
    ROLES = [(x, x) for x in ["viewer", "operator", "editor", "manager"]]
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    role = models.CharField(max_length=16, choices=ROLES)
    permissions = models.JSONField(default=list)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "project"], name="unique_membership"
            )
        ]


class Environment(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.PROTECT, related_name="environments"
    )
    name = models.CharField(max_length=120, db_collation="utf8mb4_0900_as_cs")
    archived = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "name"], name="unique_environment"
            )
        ]


class Application(models.Model):
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    name = models.CharField(max_length=180, db_collation="utf8mb4_0900_as_cs")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "name"], name="unique_application"
            )
        ]


class Machine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.PROTECT, related_name="machines"
    )
    environment = models.ForeignKey(Environment, on_delete=models.PROTECT)
    application = models.ForeignKey(
        Application, on_delete=models.PROTECT, null=True, blank=True
    )
    server_name = models.CharField(max_length=180, db_collation="utf8mb4_0900_as_cs")
    vms = models.CharField(max_length=240, blank=True)
    cpu = models.PositiveIntegerField(default=0)
    ram = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    os = models.CharField(max_length=180, blank=True)
    network = models.CharField(
        max_length=180, blank=True, db_collation="utf8mb4_0900_as_cs"
    )
    ip = models.CharField(max_length=45, blank=True)
    subnet = models.CharField(max_length=4, blank=True)
    gateway = models.CharField(max_length=45, blank=True)
    interfaces = models.JSONField(default=list, blank=True)
    username = models.CharField(max_length=180, blank=True)
    status = models.CharField(
        max_length=20,
        default="planned",
        choices=[(s, s) for s in ["planned", "in_progress", "completed", "blocked"]],
    )
    archived = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["project", "environment", "network", "ip"]),
            models.Index(fields=["project", "server_name"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ram__gte=0), name="nonnegative_ram"
            )
        ]


class Disk(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, related_name="disks")
    name = models.CharField(max_length=120)
    size = models.DecimalField(max_digits=12, decimal_places=2)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["machine", "order"], name="unique_disk_order"
            ),
            models.CheckConstraint(
                condition=models.Q(size__gt=0), name="positive_disk_size"
            ),
        ]


class Credential(models.Model):
    machine = models.OneToOneField(
        Machine, on_delete=models.PROTECT, related_name="credential"
    )
    ciphertext = models.TextField(blank=True)
    secret_reference = models.CharField(max_length=300, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class Activity(models.Model):
    machine = models.ForeignKey(
        Machine, on_delete=models.PROTECT, related_name="activities"
    )
    author = models.ForeignKey(User, on_delete=models.PROTECT)
    event = models.CharField(max_length=40)
    source = models.CharField(max_length=20, default="web")
    comment = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)


class CommentRevision(models.Model):
    activity = models.ForeignKey(
        Activity, on_delete=models.PROTECT, related_name="revisions"
    )
    author = models.ForeignKey(User, on_delete=models.PROTECT)
    previous = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Change(models.Model):
    activity = models.ForeignKey(
        Activity, on_delete=models.PROTECT, related_name="changes"
    )
    field = models.CharField(max_length=120)
    previous = models.JSONField(null=True)
    value = models.JSONField(null=True)


class ImportBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    filename = models.CharField(max_length=255)
    file = models.FileField(upload_to="imports/%Y/%m")
    worksheet = models.CharField(max_length=120, blank=True)
    mappings = models.JSONField(default=dict)
    mode = models.CharField(max_length=20, default="add_only")
    preview = models.JSONField(default=list)
    issues = models.JSONField(default=list)
    decisions = models.JSONField(default=dict)
    counts = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default="uploaded")
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)


class ExportRecord(models.Model):
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    credentials = models.BooleanField(default=False)
    kind = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)


class SystemSetting(models.Model):
    key = models.CharField(max_length=120, unique=True)
    value = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=1)


class UpdateRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    from_version = models.CharField(max_length=40)
    to_version = models.CharField(max_length=40)
    status = models.CharField(max_length=30, default="queued")
    progress = models.JSONField(default=list)
    backup_path = models.CharField(max_length=500, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Audit(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, null=True)
    event = models.CharField(max_length=80)
    target = models.CharField(max_length=200, blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['created_at', 'id'], name='audit_time_id_idx'), models.Index(fields=['event', 'created_at'], name='audit_event_time_idx')]


class UpdateUpload(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    version = models.CharField(max_length=40)
    sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=20, default='pending')
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class LoginAttempt(models.Model):
    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()


class ImportValidation(models.Model):
    batch = models.ForeignKey(
        ImportBatch, on_delete=models.PROTECT, related_name="validations"
    )
    preview_version = models.PositiveIntegerField()
    row = models.PositiveIntegerField(null=True)
    severity = models.CharField(
        max_length=10, choices=[("error", "error"), ("warning", "warning")]
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["batch", "preview_version", "severity"])]


class ImportDecision(models.Model):
    batch = models.ForeignKey(
        ImportBatch, on_delete=models.PROTECT, related_name="row_decisions"
    )
    preview_version = models.PositiveIntegerField()
    row = models.PositiveIntegerField()
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, null=True)
    action = models.CharField(
        max_length=10, choices=[("apply", "apply"), ("skip", "skip")]
    )
    fields = models.JSONField(default=dict)
    disks = models.CharField(max_length=10, blank=True)
    credential = models.CharField(max_length=10, default="preserve")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "preview_version", "row"],
                name="unique_import_decision",
            )
        ]
