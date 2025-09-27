"""
Django settings for config project (production-ready, DB-less).

- Lit .env (DEBUG, SECRET_KEY, ALLOWED_HOSTS, email, Service Fusion…)
- Sécurise automatiquement quand DEBUG=False
- Sert les fichiers statiques via STATIC_ROOT (Nginx doit pointer dessus)
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
# SECURITY WARNING: ne mets JAMAIS une clé hardcodée en prod
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-key")

# DEBUG par défaut à False en prod (mets DEBUG=True dans .env pour dev local)
DEBUG = os.getenv("DEBUG", "False").lower() in ("1", "true", "yes")

# ALLOWED_HOSTS: liste séparée par virgule dans .env (ex: blucollar.io,www.blucollar.io,3.222.120.49)
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()]

# CSRF_TRUSTED_ORIGINS: liste séparée par virgule (ex: https://blucollar.io,https://www.blucollar.io)
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# -----------------------------------------------------------------------------
# Apps / Middleware — minimal (pas de DB)
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
# Database (aucune DB utilisée)
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

# En dev tu peux garder un dossier "static" dans le repo
# En prod on collecte vers STATIC_ROOT et Nginx sert /static/ depuis ce dossier
if DEBUG:
    STATICFILES_DIRS = [BASE_DIR / "static"]
else:
    STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -----------------------------------------------------------------------------
# Sécurité (activée automatiquement si DEBUG=False)
# -----------------------------------------------------------------------------
if not DEBUG:
    # Derrière Nginx/ALB avec HTTPS
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Cookies sécurisés
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # HSTS (active-le après avoir confirmé que tout répond en HTTPS)
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))  # 1 an
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # En-têtes
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True if hasattr(__import__("django.conf").conf.settings, "SECURE_BROWSER_XSS_FILTER") else False
    X_FRAME_OPTIONS = "DENY"
    # X-Forwarded-Host
    USE_X_FORWARDED_HOST = True

# -----------------------------------------------------------------------------
# Logs (console + niveau configurable)
# -----------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.server": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "fusion": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}

# -----------------------------------------------------------------------------
# Intégrations / Config projet
# -----------------------------------------------------------------------------
# Service Fusion (Open API)
SERVICE_FUSION_BASE_URL   = os.getenv("SERVICE_FUSION_BASE_URL", "https://api.servicefusion.com").rstrip("/")
SERVICE_FUSION_API_PREFIX = os.getenv("SERVICE_FUSION_API_PREFIX", "/v1").rstrip("/")
SERVICE_FUSION_API_KEY    = os.getenv("SERVICE_FUSION_API_KEY", "")

# OAuth2 Client Credentials
SERVICE_FUSION_CLIENT_ID     = os.getenv("SERVICE_FUSION_CLIENT_ID", "")
SERVICE_FUSION_CLIENT_SECRET = os.getenv("SERVICE_FUSION_CLIENT_SECRET", "")
SERVICE_FUSION_TOKEN_URL     = os.getenv("SERVICE_FUSION_TOKEN_URL", f"{SERVICE_FUSION_BASE_URL}/oauth/access_token")

# (legacy non utilisé si OAuth OK)
SERVICE_FUSION_COMPANY_ID = os.getenv("SERVICE_FUSION_COMPANY_ID", "")
SERVICE_FUSION_USERNAME   = os.getenv("SERVICE_FUSION_USERNAME", "")
SERVICE_FUSION_PASSWORD   = os.getenv("SERVICE_FUSION_PASSWORD", "")
SERVICE_FUSION_LOGIN_URL  = os.getenv("SERVICE_FUSION_LOGIN_URL", f"{SERVICE_FUSION_BASE_URL}/api/v1/auth/login")

# LLM (liens docx/json)
LLM_API_URL = os.getenv("LLM_API_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

# Email
EMAIL_BACKEND       = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST          = os.getenv("EMAIL_HOST", "")
EMAIL_PORT          = int(os.getenv("EMAIL_PORT", "0") or 0) or None
EMAIL_USE_TLS       = os.getenv("EMAIL_USE_TLS", "False").lower() in ("1", "true", "yes")
EMAIL_USE_SSL       = os.getenv("EMAIL_USE_SSL", "False").lower() in ("1", "true", "yes")
EMAIL_HOST_USER     = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT       = int(os.getenv("EMAIL_TIMEOUT", "30"))
DEFAULT_FROM_EMAIL  = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@works-service.us")
WORKORDER_RECIPIENT = os.getenv("WORKORDER_RECIPIENT", "AI_Workorder@works-service.us")

# HTTP timeout (requests)
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "25"))
