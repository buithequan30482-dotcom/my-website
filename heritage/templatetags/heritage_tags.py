import json
import re

from django import template
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

from core.utils import vn_slugify

register = template.Library()
H3_RE = re.compile(r"<h3([^>]*)>(.*?)</h3>", re.S | re.I)


@register.filter
def img(h, size=960):
    return h.url(int(size)) if h else ""


@register.filter
def toc_items(html):
    out = []
    for i, m in enumerate(H3_RE.finditer(html or "")):
        title = strip_tags(m.group(2)).strip()
        out.append((f"muc-{i + 1}-{vn_slugify(title)[:40]}", title))
    return out


@register.filter
def with_anchors(html):
    i = [0]

    def rep(m):
        i[0] += 1
        title = strip_tags(m.group(2)).strip()
        return f'<h3 id="muc-{i[0]}-{vn_slugify(title)[:40]}"{m.group(1)}>{m.group(2)}</h3>'
    return H3_RE.sub(rep, html or "")


@register.filter
def stars(n):
    n = int(n or 0)
    return "★" * n + "☆" * (5 - n)


@register.filter
def jsonld(d, request):
    """Dữ liệu cấu trúc schema.org cho SEO (TR NFR-04)."""
    main = d.diem_chinh
    data = {
        "@context": "https://schema.org",
        "@type": ["TouristAttraction", "LandmarksOrHistoricalBuildings"],
        "name": d.ten,
        "description": strip_tags(d.tom_tat),
        "url": request.build_absolute_uri(d.get_absolute_url()),
        "isAccessibleForFree": True,
        "address": {"@type": "PostalAddress", "streetAddress": d.dia_chi_moi, "addressRegion": "Quảng Ninh",
                    "addressCountry": "VN"},
    }
    if d.anh_dai_dien:
        data["image"] = request.build_absolute_uri(d.anh_dai_dien.url())
    if main:
        data["geo"] = {"@type": "GeoCoordinates", "latitude": main.lat, "longitude": main.lng}
    s = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return mark_safe(s)


@register.simple_tag
def review_form(existing=None):
    from interactions.forms import DanhGiaForm
    if existing is not None:
        existing.init_ts()
        return existing
    f = DanhGiaForm()
    f.init_ts()
    return f
