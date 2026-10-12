import getpass
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.password_validation import validate_password
from core.models import User


class Command(BaseCommand):
    help = "Create the first administrator using an interactive hidden password prompt"

    def add_arguments(self, p):
        p.add_argument("--username", required=True)
        p.add_argument("--if-missing", action="store_true", help="Preserve an existing active administrator during installation resume")

    def handle(self, *args, **options):
        if User.objects.filter(is_superuser=True, is_active=True).exists():
            if options["if_missing"]:
                self.stdout.write("Existing administrator preserved")
                return
            raise CommandError(
                "An active administrator already exists; use changepassword for recovery"
            )
        password = getpass.getpass("Administrator password: ")
        if password != getpass.getpass("Confirm password: "):
            raise CommandError("Passwords differ")
        u = User(username=options["username"], is_superuser=True, is_staff=True)
        validate_password(password, u)
        u.set_password(password)
        u.full_clean()
        u.save()
        self.stdout.write("Administrator created")
