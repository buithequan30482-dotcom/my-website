"""Đếm lượt xem phía máy chủ: tổng hợp theo ngày, không lưu IP, không cookie theo dõi (TR 5.5)."""
import re

from django.db.models import F
from django.utils import timezone, translation

BOT_RE = re.compile(r"bot|crawl|spider|slurp|facebookexternalhit|preview|monitor|curl|wget|python-requests|headless",
                    re.I)


def device_of(ua: str) -> str:
    ua = ua.lower()
    if "ipad" in ua or "tablet" in ua:
        return "tablet"
    if "mobi" in ua or "android" in ua or "iphone" in ua:
        return "mobile"
    return "desktop"


def track(request, di_tich=None):
    from heritage.models import DiTich
    from .models import LuotXem

    if request.method != "GET":
        return
    ua = request.META.get("HTTP_USER_AGENT", "")
    if not ua or BOT_RE.search(ua):
        return
    if getattr(request, "user", None) is not None and request.user.is_authenticated and request.user.is_staff:
        return  # không đếm cán bộ quản trị
    lang = translation.get_language() or "vi"
    path = request.path[:300]
    obj, _ = LuotXem.objects.get_or_create(
        ngay=timezone.localdate(), duong_dan=path, ngon_ngu=lang, thiet_bi=device_of(ua),
        defaults={"di_tich": di_tich, "so_luot": 0})
    LuotXem.objects.filter(pk=obj.pk).update(so_luot=F("so_luot") + 1)
    if di_tich is not None:
        DiTich.objects.filter(pk=di_tich.pk).update(luot_xem=F("luot_xem") + 1)
