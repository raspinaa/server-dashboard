# Isolated test defaults. Never import from production settings entry point.
import os
from cryptography.fernet import Fernet

for key, value in {
    "DEBUG": "1",
    "DJANGO_SECRET_KEY": "isolated-test-key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "ALLOWED_HOSTS": "testserver,localhost,127.0.0.1",
    "CREDENTIAL_KEY": Fernet.generate_key().decode(),
    "MYSQL_HOST": "127.0.0.1",
    "MYSQL_PORT": "33306",
    "MYSQL_USER": "root",
    "MYSQL_PASSWORD": "isolated-test-root",
}.items():
    os.environ.setdefault(key, value)
from .settings import *
