"""Điểm kiểm tra sống cho giám sát uptime và healthcheck Docker.

GET /healthz -> 200 "ok" khi kết nối được CSDL; 503 "db error" nếu không.
Không truy cập phiên, không ghi CSDL, không cache.

Người tích hợp gắn URL NGOÀI i18n_patterns trong config/urls.py (không có tiền tố ngôn ngữ):
    from core.health import healthz
    urlpatterns = [path("healthz", healthz, name="healthz"), ...]
"""
import logging

from django.db import connection
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

logger = logging.getLogger(__name__)


@never_cache
@require_safe
def healthz(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # noqa: BLE001 - mọi lỗi CSDL đều là "không khỏe"
        logger.exception("healthz: không kết nối được CSDL")
        return HttpResponse("db error\n", status=503, content_type="text/plain; charset=utf-8")
    return HttpResponse("ok\n", content_type="text/plain; charset=utf-8")
