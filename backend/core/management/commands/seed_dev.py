from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core.models import User, Project, Environment
from core.inventory import save_machine


class Command(BaseCommand):
    help = "Create sanitized local UI test data; requires DEBUG=1"

    @transaction.atomic
    def handle(self, *args, **opts):
        if not settings.DEBUG:
            raise CommandError("Refused outside local development")
        if User.objects.filter(username="demo-admin").exists():
            self.stdout.write("Seed already exists")
            return
        u = User.objects.create_user(
            username="demo-admin",
            password="Isolated-Demo-Password-2026!",
            is_superuser=True,
            is_staff=True,
        )
        p = Project.objects.create(
            name="پروژه نمونه",
            description="داده‌های کاملاً ساختگی برای توسعه",
            created_by=u,
        )
        for name in ["Develop", "Test"]:
            Environment.objects.create(project=p, name=name)
        for i in range(1, 5):
            save_machine(
                u,
                p,
                {
                    "server_name": f"sample-node-{i}",
                    "environment": p.environments.get(
                        name="Develop" if i < 3 else "Test"
                    ).id,
                    "application": "Sample Service",
                    "vms": f"Worker {i}",
                    "cpu": i * 2,
                    "ram": str(i * 4),
                    "os": "Ubuntu 24.04",
                    "network": "VLAN 100",
                    "ip": f"192.0.2.{10 + i}",
                    "subnet": "/24",
                    "gateway": "192.0.2.1",
                    "username": "sample",
                    "disks": [
                        {"name": f"volume-{j}", "size": str(j * 20), "order": j - 1}
                        for j in range(1, i + 1)
                    ],
                },
            )
        self.stdout.write("Sanitized development seed created; no machine passwords")
