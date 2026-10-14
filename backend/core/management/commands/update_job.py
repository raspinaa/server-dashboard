import json, sys
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import UpdateRun, UpdateUpload, SystemSetting
from core.security import audit


class Command(BaseCommand):
    help = (
        "Internal CLI for the narrowly scoped deployment helper; never an HTTP endpoint"
    )

    def add_arguments(self, p):
        p.add_argument(
            "action", choices=["claim", "progress", "finish", "fail", "recover", "claim_upload", "upload_ready", "upload_fail"]
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        data = json.loads(sys.stdin.read() or "{}")
        action = opts["action"]
        if action == 'claim_upload':
            SystemSetting.objects.get_or_create(key='update_lock', defaults={'value': {}})
            SystemSetting.objects.select_for_update().get(key='update_lock')
            upload = UpdateUpload.objects.select_for_update().filter(status='pending').order_by('created_at').first()
            if not upload:
                self.stdout.write('{}'); return
            if not upload.user.is_active or not (upload.user.is_superuser or 'perform_updates' in upload.user.independent_permissions):
                upload.status='failed'; upload.error='مجوز به‌روزرسانی لغو شده است'; upload.save()
                audit(upload.user, 'update_upload_failed', upload.id, reason='permission_revoked')
                self.stdout.write('{}'); return
            upload.status='processing'; upload.save()
            self.stdout.write(json.dumps({'id':str(upload.id), 'version':upload.version, 'sha256':upload.sha256})); return
        if action in ['upload_ready', 'upload_fail']:
            upload = UpdateUpload.objects.select_for_update().get(id=data['id'], status='processing')
            upload.status='ready' if action=='upload_ready' else 'failed'
            upload.error='' if action=='upload_ready' else 'بسته روی سرور تأیید نشد؛ گزارش سرویس بررسی شود'
            if action=='upload_ready':
                from core.updates import check_release
                check_release(upload.user)
            upload.save()
            audit(upload.user, 'update_upload_ready' if action=='upload_ready' else 'update_upload_failed', upload.id, version=upload.version)
            self.stdout.write('{}'); return
        if action == "recover":
            UpdateUpload.objects.filter(status='processing').update(status='failed', error='بررسی بسته با راه‌اندازی مجدد سرویس متوقف شد؛ فایل را دوباره بارگذاری کنید')
            for r in UpdateRun.objects.select_for_update().filter(status="running"):
                r.status = "failed"
                r.error = "Helper restarted during update; inspect journal/backup before retry"
                r.save()
                audit(r.user, "update_interrupted", r.id)
            self.stdout.write("{}")
            return
        if action == "claim":
            run = (
                UpdateRun.objects.select_for_update()
                .filter(status="queued")
                .order_by("created_at")
                .first()
            )
            if not run:
                self.stdout.write("{}")
                return
            # Recheck permission at execution time, including account revocation.
            if not run.user.is_active or not (
                run.user.is_superuser
                or "perform_updates" in run.user.independent_permissions
            ):
                run.status = "failed"
                run.error = "Update permission revoked"
                run.save()
                self.stdout.write("{}")
                return
            run.status = "running"
            run.save()
            self.stdout.write(
                json.dumps({"id": str(run.id), "version": run.to_version})
            )
            return
        run = UpdateRun.objects.select_for_update().get(id=data["id"], status="running")
        if action == "finish":
            run.status = "completed"
            run.progress = data.get("progress", [])
            run.backup_path = data.get("backup", "")
            audit(run.user, "update_completed", run.id, version=run.to_version)
        elif action == "fail":
            run.status = "failed"
            run.error = "Deployment failed; inspect helper journal"
            audit(run.user, "update_failed", run.id)
        else:
            run.progress = data.get("progress", [])
        run.save()
        self.stdout.write("{}")
