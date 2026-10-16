from django.conf import settings
from django.urls import translate_url
from django.utils import translation

from .models import SiteConfig


def site(request):
    cfg = SiteConfig.get()
    cur = translation.get_language() or "vi"
    path = request.get_full_path()
    langs = [{"code": c, "name": n, "short": {"vi": "VI", "en": "EN", "zh-hans": "中文"}.get(c, c),
              "url": translate_url(path, c), "current": c == cur} for c, n in settings.LANGUAGES]
    rm = getattr(request, "resolver_match", None)
    return {
        "site_cfg": cfg,
        "MAPS_KEY": cfg.maps_key,
        "ADMIN_URL": settings.ADMIN_URL,
        "lang_links": langs,
        "cur_lang": cur,
        "url_name": rm.url_name if rm else "",
    }
