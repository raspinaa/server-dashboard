import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv("DEBUG", "0") == "1"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be configured (at least 32 characters)"
    )
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
CSRF_TRUSTED_ORIGINS = [
    x for x in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if x
]
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.MaintenanceMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_DATABASE", "infrahub"),
        "USER": os.getenv("MYSQL_USER", "infrahub"),
        "PASSWORD": os.getenv("MYSQL_PASSWORD", ""),
        "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "PORT": os.getenv("MYSQL_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'",
            "isolation_level": "read committed",
        },
        "TEST": {"CHARSET": "utf8mb4", "COLLATION": "utf8mb4_0900_as_cs"},
    }
}
AUTH_USER_MODEL = "core.User"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "fa-ir"
TIME_ZONE = "Asia/Tehran"
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(BASE_DIR / "media")))
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("UPLOAD_LIMIT_MB", "10")) * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = DATA_UPLOAD_MAX_MEMORY_SIZE
# Transport mode is explicit. Production defaults to TLS; "none" is an operator
# choice for trusted HTTP networks, never an automatic certificate fallback.
TLS_MODE = os.getenv("TLS_MODE", "letsencrypt")
if TLS_MODE not in {"letsencrypt", "local", "none", "custom"}:
    raise ImproperlyConfigured("Invalid TLS_MODE")
TRANSPORT_SECURE = not DEBUG and TLS_MODE != "none"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = TRANSPORT_SECURE
CSRF_COOKIE_SECURE = TRANSPORT_SECURE
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = int(os.getenv("SESSION_SECONDS", "3600"))
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000 if TRANSPORT_SECURE else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = TRANSPORT_SECURE
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication"
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "EXCEPTION_HANDLER": "core.api.exception_handler",
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
}
CREDENTIAL_KEY = os.getenv("CREDENTIAL_KEY", "")
RELEASE_REPOSITORY = os.getenv("RELEASE_REPOSITORY", "")
RELEASE_CHANNEL = os.getenv("RELEASE_CHANNEL", "stable")
RELEASE_PUBLIC_KEY = os.getenv("RELEASE_PUBLIC_KEY", "")
UPDATE_STATE = Path(os.getenv("UPDATE_STATE", str(BASE_DIR / "state")))
UPDATE_EXECUTION_ENABLED = os.getenv("UPDATE_EXECUTION_ENABLED", "0") == "1"

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Fail closed on production credentials rather than running with an unusable key.
if not DEBUG:
    from cryptography.fernet import Fernet

    try:
        Fernet(CREDENTIAL_KEY.encode())
    except (ValueError, TypeError):
        raise ImproperlyConfigured(
            "A valid separately managed CREDENTIAL_KEY is required"
        )

SECURE_SSL_REDIRECT = TRANSPORT_SECURE
SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]
