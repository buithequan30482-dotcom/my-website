"""Cấu hình Website di tích Đặc khu Vân Đồn.

Mọi giá trị nhạy cảm đọc từ biến môi trường (file .env khi chạy Docker).
"""
import os
from pathlib import Path

import dj_database_url
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return str(env(name, default)).lower() in ("1", "true", "yes", "on")


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

# Đường dẫn khu quản trị không dùng /admin/ mặc định (TR mục 3.2)
ADMIN_URL = env("ADMIN_URL", "quan-tri-vd/").strip("/") + "/"

INSTALLED_APPS = [
    "modeltranslation",  # phải đứng trước django.contrib.admin
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.humanize",
    "core",
    "heritage",
    "interactions",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.AdminOTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
    "core.middleware.AuditUserMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=env("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=60,
        conn_health_checks=True,  # kết nối giữ lâu bị DB đóng (khởi động lại db) -> tự mở lại
    )
}

REDIS_URL = env("REDIS_URL")
if REDIS_URL:
    CACHES = {"default": {"BACKEND": "django_redis.cache.RedisCache", "LOCATION": REDIS_URL}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---- Ngôn ngữ (TR FR-P01) ----
LANGUAGE_CODE = "vi"
LANGUAGES = [
    ("vi", "Tiếng Việt"),
    ("en", "English"),
    ("zh-hans", "中文"),
]
MODELTRANSLATION_DEFAULT_LANGUAGE = "vi"
MODELTRANSLATION_FALLBACK_LANGUAGES = ("vi",)
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = Path(env("STATIC_ROOT", BASE_DIR / "staticfiles"))  # image Docker: /app/staticfiles
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage" if not DEBUG else "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", BASE_DIR / "media"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATA_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# ---- Bảo mật (TR 8.2) ----
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 8
CSRF_COOKIE_HTTPONLY = False
X_FRAME_OPTIONS = "SAMEORIGIN"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
if env_bool("DJANGO_HTTPS", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False

LOGIN_MAX_FAILS = 5          # khóa tạm sau 5 lần sai
LOGIN_LOCK_MINUTES = 15
OTP_REQUIRED_FOR_SUPERUSER = env_bool("OTP_REQUIRED_FOR_SUPERUSER", True)

# ---- Email ----
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = int(env("EMAIL_PORT", 587))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "noreply@localhost")

# ---- Tương tác (TR FR-I06) ----
SUBMIT_RATE_LIMIT_PER_HOUR = int(env("SUBMIT_RATE_LIMIT_PER_HOUR", 5))
MIN_FORM_SECONDS = 3

# ---- Bản đồ (TR mục 6) ----
# Khóa Google Maps có thể đặt ở đây hoặc trong Cấu hình hệ thống (khu quản trị).
GOOGLE_MAPS_API_KEY = env("GOOGLE_MAPS_API_KEY", "")
MAP_BOUNDS = {"south": 20.55, "west": 106.95, "north": 21.65, "east": 108.15}  # quanh Quảng Ninh
VANDON_BOUNDS = {"south": 20.70, "west": 107.20, "north": 21.25, "east": 107.70}

# ---- Nhật ký (triển khai): ghi ra stdout -> `docker compose logs web`; lỗi 500 gửi email cho DJANGO_ADMINS ----
from email.utils import getaddresses  # noqa: E402

ADMINS = [(n or e, e) for n, e in getaddresses([env("DJANGO_ADMINS", "")]) if e]
SERVER_EMAIL = env("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s", "datefmt": "%Y-%m-%d %H:%M:%S"},
    },
    "filters": {"require_debug_false": {"()": "django.utils.log.RequireDebugFalse"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
        "mail_admins": {
            "class": "django.utils.log.AdminEmailHandler",
            "level": "ERROR",
            "filters": ["require_debug_false"],
        },
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.request": {"handlers": ["console", "mail_admins"], "level": "ERROR", "propagate": False},
        # Host header sai (quét tự động) – không gửi email, chỉ ghi nhật ký
        "django.security.DisallowedHost": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
AUTHENTICATION_BACKENDS = ["core.backends.LockoutBackend"]
