"""
Django settings for config project (production-ready, DB-less).

- Reads environment variables from .env (DEBUG, SECRET_KEY, ALLOWED_HOSTS, email, Service Fusion, etc.)
- Applies secure headers automatically when DEBUG=False
- Serves static files via STATIC_ROOT (Nginx must point /static/ to STATIC_ROOT)
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# Paths / .env
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# -----------------------------------------------------------------------------
# Core
# -----------------------------------------------------------------------------
# WARNING: never hardcode a production key in code
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-key")

# Default to False in production; set DEBUG=True in .env only for local/dev
DEBUG = os.getenv("DEBUG", "False").lower() in ("1", "true", "yes")

# ALLOWED_HOSTS: comma-separated in .env (e.g. blucollar.io,www.blucollar.io,3.222.120.49)
_raw_hosts = os.getenv("ALLOWED_HOSTS", "" if not DEBUG else "localhost,127.0.0.1,0.0.0.0")
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(",") if h.strip()]

# CSRF_TRUSTED_ORIGINS: comma-separated (must include scheme, e.g. https://blucollar.io)
_raw_csrf = os.getenv("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _raw_csrf.split(",") if o.strip()]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# -----------------------------------------------------------------------------
# Apps / Middleware — minimal footprint (no DB)
# -----------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "fusion",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

# -----------------------------------------------------------------------------
# Templates
# -----------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

# -----------------------------------------------------------------------------
# Database (unused)
# -----------------------------------------------------------------------------
DATABASES = {}

# -----------------------------------------------------------------------------
# I18N
# -----------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# -----------------------------------------------------------------------------
# Static / Media
# -----------------------------------------------------------------------------
STATIC_URL = "/static/"
# Always define STATIC_ROOT; collectstatic will write here in production
STATIC_ROOT = BASE_DIR / "staticfiles"

# In dev you may also keep a "static" directory inside the repo
_static_dir = BASE_DIR / "static"
if DEBUG and _static_dir.exists():
    STATICFILES_DIRS = [ _static_dir ]  # noqa: F405

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -----------------------------------------------------------------------------
# Security (auto-applied when DEBUG=False)
# -----------------------------------------------------------------------------
if not DEBUG:
    # Behind Nginx/ALB terminating TLS
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

    # Cookies security
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"

    # HSTS – enable after HTTPS is confirmed working
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Extra headers
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = os.getenv("SECURE_REFERRER_POLICY", "same-origin")
    X_FRAME_OPTIONS = "DENY"

# -----------------------------------------------------------------------------
# Logging (console; level configurable)
# -----------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.server": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "django.security": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "fusion": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}

# -----------------------------------------------------------------------------
# Project integrations
# -----------------------------------------------------------------------------
# Service Fusion (Open API)
SERVICE_FUSION_BASE_URL   = os.getenv("SERVICE_FUSION_BASE_URL", "https://api.servicefusion.com").rstrip("/")
SERVICE_FUSION_API_PREFIX = os.getenv("SERVICE_FUSION_API_PREFIX", "/v1").rstrip("/")
SERVICE_FUSION_API_KEY    = os.getenv("SERVICE_FUSION_API_KEY", "")

# OAuth2 Client Credentials
SERVICE_FUSION_CLIENT_ID     = os.getenv("SERVICE_FUSION_CLIENT_ID", "")
SERVICE_FUSION_CLIENT_SECRET = os.getenv("SERVICE_FUSION_CLIENT_SECRET", "")
SERVICE_FUSION_TOKEN_URL     = os.getenv("SERVICE_FUSION_TOKEN_URL", f"{SERVICE_FUSION_BASE_URL}/oauth/access_token")

# (legacy; not used when OAuth works)
SERVICE_FUSION_COMPANY_ID = os.getenv("SERVICE_FUSION_COMPANY_ID", "")
SERVICE_FUSION_USERNAME   = os.getenv("SERVICE_FUSION_USERNAME", "")
SERVICE_FUSION_PASSWORD   = os.getenv("SERVICE_FUSION_PASSWORD", "")
SERVICE_FUSION_LOGIN_URL  = os.getenv("SERVICE_FUSION_LOGIN_URL", f"{SERVICE_FUSION_BASE_URL}/api/v1/auth/login")

# LLM (docx/json links)
LLM_API_URL = os.getenv("LLM_API_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

# Email (SMTP)
EMAIL_BACKEND       = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST          = os.getenv("EMAIL_HOST", "")
_email_port         = os.getenv("EMAIL_PORT", "").strip()
EMAIL_PORT          = int(_email_port) if _email_port.isdigit() else None
EMAIL_USE_TLS       = os.getenv("EMAIL_USE_TLS", "False").lower() in ("1", "true", "yes")
EMAIL_USE_SSL       = os.getenv("EMAIL_USE_SSL", "False").lower() in ("1", "true", "yes")
EMAIL_HOST_USER     = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT       = int(os.getenv("EMAIL_TIMEOUT", "30"))
DEFAULT_FROM_EMAIL  = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@works-service.us")
WORKORDER_RECIPIENT = os.getenv("WORKORDER_RECIPIENT", "AI_Workorder@works-service.us")

# HTTP client timeout (requests)
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "25"))
