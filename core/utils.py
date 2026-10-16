"""Tiện ích dùng chung: bỏ dấu tiếng Việt, slug, chuyển đổi tọa độ DMS, khoảng cách."""
import hashlib
import math
import re
import unicodedata

from django.conf import settings


def strip_accents(text: str) -> str:
    """'Đền Cửa Ông' -> 'den cua ong' (dùng cho tìm kiếm không dấu)."""
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text).strip().lower()


def vn_slugify(text: str, max_length: int = 200) -> str:
    s = strip_accents(text)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:max_length].strip("-") or "di-tich"


DMS_RE = re.compile(
    r"(\d{1,3})\s*[°º]\s*(\d{1,2})\s*['’′]\s*(\d{1,2}(?:[.,]\d+)?)\s*[\"”″]?\s*([NSns])"
    r"[\s,;]*"
    r"(\d{1,3})\s*[°º]\s*(\d{1,2})\s*['’′]\s*(\d{1,2}(?:[.,]\d+)?)\s*[\"”″]?\s*([EWew])"
)
DEC_RE = re.compile(r"^\s*(-?\d{1,3}(?:[.,]\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:[.,]\d+)?)\s*$")


class CoordinateError(ValueError):
    pass


def _dms_to_dec(d, m, s, hemi):
    d, m, s = float(d), float(m), float(str(s).replace(",", "."))
    note = ""
    if s >= 60:  # ví dụ 48'60.0" trong danh mục -> 49'00"
        s -= 60
        m += 1
        note = 'Đã chuẩn hóa giây ≥ 60'
    if m >= 60:
        m -= 60
        d += 1
    val = d + m / 60 + s / 3600
    if hemi.upper() in ("S", "W"):
        val = -val
    return val, note


def parse_coordinates(text: str):
    """Nhận chuỗi DMS (20°53'49.3"N 107°18'33.7"E) hoặc thập phân (20.897, 107.309).

    Trả về (lat, lng, ghi_chu). Ném CoordinateError nếu không đọc được.
    """
    if not text or not text.strip():
        raise CoordinateError("Chưa nhập tọa độ.")
    t = text.strip()
    m = DMS_RE.search(t)
    if m:
        lat, n1 = _dms_to_dec(m.group(1), m.group(2), m.group(3), m.group(4))
        lng, n2 = _dms_to_dec(m.group(5), m.group(6), m.group(7), m.group(8))
        note = n1 or n2
    else:
        m = DEC_RE.match(t)
        if not m:
            raise CoordinateError(
                'Không đọc được tọa độ. Ví dụ hợp lệ: 20°53\'49.3"N 107°18\'33.7"E hoặc 20.897028, 107.309361'
            )
        lat = float(m.group(1).replace(",", "."))
        lng = float(m.group(2).replace(",", "."))
        note = ""
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise CoordinateError("Tọa độ vượt giới hạn hợp lệ.")
    return round(lat, 6), round(lng, 6), note


def in_van_don(lat, lng) -> bool:
    b = settings.VANDON_BOUNDS
    return b["south"] <= lat <= b["north"] and b["west"] <= lng <= b["east"]


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def hash_ip(ip: str) -> str:
    """Băm IP kèm SECRET_KEY: không lưu IP gốc (TR 4.3)."""
    return hashlib.sha256(f"{settings.SECRET_KEY}:{ip}".encode()).hexdigest()[:32]


def client_ip(request) -> str:
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


# ---- Làm sạch HTML do biên tập viên nhập (chống XSS) ----
ALLOWED_TAGS = {"h2", "h3", "h4", "p", "br", "ul", "ol", "li", "strong", "b", "em", "i", "u", "blockquote", "a", "img",
                "figure", "figcaption", "table", "thead", "tbody", "tr", "th", "td", "code", "kbd"}
ALLOWED_ATTRS = {"a": ["href", "title", "target", "rel"], "img": ["src", "alt", "width", "height", "loading"],
                 "th": ["colspan", "rowspan"], "td": ["colspan", "rowspan"]}


def clean_html(html: str) -> str:
    import bleach
    if not html:
        return html
    out = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, protocols=["http", "https", "mailto", "tel"],
                       strip=True, strip_comments=True)
    return out.replace("<p><br></p>", "").strip()


def clean_html_fields(obj, base_fields, langs=("vi", "en", "zh_hans")):
    for f in base_fields:
        for name in [f] + [f"{f}_{l}" for l in langs]:
            if hasattr(obj, name) and isinstance(getattr(obj, name), str):
                setattr(obj, name, clean_html(getattr(obj, name)))
