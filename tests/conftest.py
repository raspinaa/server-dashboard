import os
from pathlib import Path
from cryptography.fernet import Fernet

os.environ.setdefault(
    "DJANGO_SECRET_KEY", "isolated-test-key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
)
os.environ.setdefault("DEBUG", "1")
os.environ.setdefault("ALLOWED_HOSTS", "testserver,localhost,127.0.0.1")
os.environ.setdefault("CREDENTIAL_KEY", Fernet.generate_key().decode())
os.environ.setdefault("MYSQL_HOST", "127.0.0.1")
os.environ.setdefault("MYSQL_PORT", "33306")
os.environ.setdefault("MYSQL_USER", "root")
os.environ.setdefault("MYSQL_PASSWORD", "isolated-test-root")
import pytest
from rest_framework.test import APIClient
from core.models import User, Project, Environment, Membership


@pytest.fixture
def setup(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "uploads"
    settings.UPDATE_STATE = tmp_path / "state"
    admin = User.objects.create_user(
        username="admin",
        password="Test-local-only-password-123!",
        is_superuser=True,
        is_staff=True,
    )
    project = Project.objects.create(name="نمونه", created_by=admin)
    env = Environment.objects.create(project=project, name="Develop")
    second = Project.objects.create(name="دیگر", created_by=admin)
    Environment.objects.create(project=second, name="Test")
    return admin, project, env, second


@pytest.fixture
def client(setup):
    c = APIClient()
    c.force_authenticate(setup[0])
    return c
