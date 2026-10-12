import json, sys
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import UpdateRun
from core.security import audit


class Command(BaseCommand):
    help = (
        "Internal CLI for the narrowly scoped deployment helper; never an HTTP endpoint"
    )

    def add_arguments(self, p):
        p.add_argument(
            "action", choices=["claim", "progress", "finish", "fail", "recover"]
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        data = json.loads(sys.stdin.read() or "{}")
        action = opts["action"]
        if action == "recover":
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
