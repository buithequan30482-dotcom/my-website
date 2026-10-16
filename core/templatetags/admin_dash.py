"""Số liệu cho trang chủ khu quản trị (TR FR-A02).

    {% load admin_dash %}
    {% admin_dashboard as dash %}

Trả về dict: `tiles` (ô số liệu), `todo` (việc cần làm), `shortcuts` (lối tắt). Mỗi khối chỉ có mục
mà người dùng có quyền xem.
"""
import re

from django import template
from django.contrib import admin
from django.db.models import Exists, OuterRef, Q
from django.urls import NoReverseMatch, reverse

register = template.Library()

# Tên URL có thể có của chức năng "Nhập từ Excel" (do phần quản trị di tích định nghĩa).
EXCEL_URL_NAMES = ["admin:heritage_ditich_import", "admin:heritage_ditich_import_excel",
                   "admin:heritage_ditich_nhap_excel", "admin:heritage_import_excel"]


def _url(name, query="", *args):
    try:
        return reverse(name, args=args) + query
    except NoReverseMatch:
        return None


def _first_url(names):
    for n in names:
        u = _url(n)
        if u:
            return u
    return None


def _ids_query(ids, limit=200):
    """?id__in=1,2,3 – lọc changelist theo danh sách id (admin cho phép lookup trên trường của chính model)."""
    ids = list(ids)[:limit]
    return "?id__in=" + ",".join(str(i) for i in ids) if ids else ""


def ditich_gaps():
    """Danh sách id di tích (chưa ẩn) thiếu ảnh thật / tọa độ / bản dịch."""
    from heritage.models import DiemDiTich, DiTich, HinhAnh, TrangThai

    qs = DiTich.objects.exclude(trang_thai=TrangThai.HIDDEN)
    real_photo = HinhAnh.objects.filter(di_tich=OuterRef("pk"), la_minh_hoa=False)
    has_coord = DiemDiTich.objects.filter(di_tich=OuterRef("pk"), vi_do__isnull=False, kinh_do__isnull=False)
    no_photo = list(qs.filter(~Exists(real_photo)).values_list("id", flat=True))
    no_coord = list(qs.filter(~Exists(has_coord)).values_list("id", flat=True))
    no_en = Q(tom_tat_en__isnull=True) | Q(tom_tat_en="")
    no_zh = Q(tom_tat_zh_hans__isnull=True) | Q(tom_tat_zh_hans="")
    no_tr = list(qs.filter(no_en | no_zh).values_list("id", flat=True))
    return {"no_photo": no_photo, "no_coord": no_coord, "no_translation": no_tr}


# Bộ lọc tùy biến của DiTichAdmin (heritage/admin.py): (tham số, giá trị). Thẻ số liệu liên kết tới
# changelist đã lọc bằng đúng các tham số này và đếm bằng chính queryset của bộ lọc để số khớp với danh sách.
GAP_FILTERS = {
    "no_coord": ("toa_do", "thieu"),
    "no_photo": ("anh", "minh_hoa"),
    "no_translation": ("ban_dich", "thieu"),
}


def _ditich_filtered(request, param, value):
    """Số bản ghi của changelist di tích khi áp bộ lọc `param=value`; None nếu bộ lọc chưa có."""
    from heritage.models import DiTich
    ma = admin.site._registry.get(DiTich)
    if ma is None or request is None:
        return None
    for f in ma.list_filter:
        if isinstance(f, type) and issubclass(f, admin.SimpleListFilter) and f.parameter_name == param:
            try:
                flt = f(request, {param: [value]}, DiTich, ma)
                return flt.queryset(request, ma.get_queryset(request)).count()
            except Exception:  # pragma: no cover - không để trang chủ lỗi vì bộ lọc của phần khác
                return None
    return None


@register.simple_tag(takes_context=True)
def admin_dashboard(context):
    request = context.get("request")
    user = getattr(request, "user", None) or context.get("user")
    if user is None or not user.is_authenticated:
        return {"tiles": [], "todo": [], "shortcuts": []}

    def can(perm):
        return user.is_superuser or user.has_perm(perm)

    tiles, todo, shortcuts = [], [], []
    ditich_list = _url("admin:heritage_ditich_changelist")

    # ---- Di tích ----
    if can("heritage.view_ditich"):
        from heritage.models import DiTich, TrangThai
        counts = {k: 0 for k in TrangThai.values}
        for row in DiTich.objects.values_list("trang_thai", flat=True):
            counts[row] = counts.get(row, 0) + 1
        q = lambda s: (ditich_list + f"?trang_thai__exact={s}") if ditich_list else None  # noqa: E731
        tiles += [
            {"label": "Di tích đã xuất bản", "value": counts.get(TrangThai.PUBLISHED, 0), "tone": "ngoc",
             "url": q(TrangThai.PUBLISHED), "group": "ditich"},
            {"label": "Di tích bản nháp", "value": counts.get(TrangThai.DRAFT, 0), "tone": "da",
             "url": q(TrangThai.DRAFT), "group": "ditich"},
            {"label": "Di tích chờ duyệt", "value": counts.get(TrangThai.REVIEW, 0), "tone": "dong",
             "url": q(TrangThai.REVIEW), "group": "ditich"},
        ]
        gaps = None
        for key, label, hint, tone in [
            ("no_coord", "Di tích thiếu tọa độ", "Có điểm chưa nhập vĩ độ, kinh độ", "dong"),
            ("no_photo", "Di tích chỉ có ảnh minh họa", "Cần thay bằng ảnh chụp thực tế", "dong"),
            ("no_translation", "Di tích thiếu bản dịch EN/ZH", "Chưa có tóm tắt tiếng Anh hoặc tiếng Trung", "da"),
        ]:
            param, val = GAP_FILTERS[key]
            n = _ditich_filtered(request, param, val)
            if n is not None:
                url = ditich_list and f"{ditich_list}?{param}={val}"
            else:  # bộ lọc chưa có: đếm trực tiếp và lọc theo danh sách id
                gaps = gaps or ditich_gaps()
                n = len(gaps[key])
                url = ditich_list and ditich_list + _ids_query(gaps[key])
            tiles.append({"label": label, "value": n, "tone": tone if n else "ngoc", "url": url, "group": "ditich"})
            if n:
                todo.append({"prio": 5, "label": label, "hint": hint, "count": n, "tone": "dong", "url": url})

    # ---- Tương tác ----
    if can("interactions.view_danhgia"):
        from interactions.models import DanhGia, TrangThaiDuyet
        pending = DanhGia.objects.filter(trang_thai=TrangThaiDuyet.PENDING).count()
        mod = _url("dashboard:moderation")
        dl = _url("admin:interactions_danhgia_changelist")
        tiles.append({"label": "Nhận xét chờ duyệt", "value": pending, "tone": "ngoc" if not pending else "dong",
                      "url": (dl and dl + "?trang_thai__exact=pending") or mod, "group": "tuongtac"})
        if pending:
            spam = DanhGia.objects.filter(trang_thai=TrangThaiDuyet.PENDING, nghi_spam=True).count()
            todo.append({"prio": 2, "label": "Nhận xét chờ duyệt", "count": pending, "tone": "ngoc", "url": mod,
                            "hint": f"{spam} nhận xét nghi spam" if spam else "Duyệt trước khi hiển thị công khai"})
    if can("interactions.view_gopy"):
        from interactions.models import GopY
        gl = _url("admin:interactions_gopy_changelist")
        moi = GopY.objects.filter(trang_thai=GopY.XuLy.MOI).count()
        xc = GopY.objects.filter(loai=GopY.Loai.XUONG_CAP, trang_thai__in=[GopY.XuLy.MOI, GopY.XuLy.DANG]).count()
        tiles.append({"label": "Góp ý mới", "value": moi, "tone": "dong" if moi else "ngoc",
                      "url": gl and gl + "?trang_thai__exact=moi", "group": "tuongtac"})
        tiles.append({"label": "Báo xuống cấp chưa xử lý", "value": xc, "tone": "son" if xc else "ngoc",
                      "url": gl and gl + "?loai__exact=xuong_cap&trang_thai__in=moi,dang", "group": "tuongtac"})
        if xc:
            todo.append({"prio": 1, "label": "Báo di tích xuống cấp chưa xử lý", "count": xc, "tone": "son",
                            "hint": "Cần kiểm tra hiện trường, phản hồi người gửi",
                            "url": gl and gl + "?loai__exact=xuong_cap&trang_thai__in=moi,dang"})
        if moi:
            todo.append({"prio": 3, "label": "Góp ý mới", "count": moi, "tone": "ngoc", "hint": "Nhận xử lý và phản hồi",
                         "url": gl and gl + "?trang_thai__exact=moi"})
    todo.sort(key=lambda t: t["prio"])

    # ---- Lối tắt ----
    if can("heritage.add_ditich"):
        wiz = _url("admin:heritage_ditich_wizard") or _url("admin:heritage_ditich_add")
        if wiz:
            shortcuts.append({"label": "Thêm di tích (từng bước)", "url": wiz, "icon": "plus", "primary": True})
    if can("heritage.change_ditich") and ditich_list:
        shortcuts.append({"label": "Tải ảnh", "url": ditich_list, "icon": "image",
                          "hint": "Mở di tích → thẻ Ảnh, video"})
    if can("heritage.add_ditich"):
        xl = _first_url(EXCEL_URL_NAMES)
        if xl:
            shortcuts.append({"label": "Nhập từ Excel", "url": xl, "icon": "table"})
    if can("interactions.change_danhgia"):
        u = _url("dashboard:moderation")
        if u:
            shortcuts.append({"label": "Kiểm duyệt nhanh", "url": u, "icon": "check",
                              "hint": "Duyệt nhận xét bằng phím tắt"})
    if can("interactions.view_danhgia"):
        u = _url("dashboard:index")
        if u:
            shortcuts.append({"label": "Thống kê", "url": u, "icon": "chart"})
    shortcuts.append({"label": "Hướng dẫn sử dụng", "url": _url("core:help"), "icon": "help"})
    return {"tiles": tiles, "todo": todo, "shortcuts": shortcuts,
            "tiles_tuongtac": [t for t in tiles if t.get("group") == "tuongtac"],
            "tiles_ditich": [t for t in tiles if t.get("group") == "ditich"]}


@register.filter
def so_vn(n):
    """1234 -> 1.234"""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return n


_YT_RE = re.compile(r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})")


@register.filter
def youtube_embed(url):
    """Liên kết YouTube -> URL nhúng youtube-nocookie; chuỗi rỗng nếu không phải YouTube."""
    m = _YT_RE.search(url or "")
    return f"https://www.youtube-nocookie.com/embed/{m.group(1)}?rel=0" if m else ""


@register.simple_tag
def help_neighbors(articles, current):
    """(bài trước, bài sau) của `current` trong danh sách."""
    items = list(articles)
    ids = [a.pk for a in items]
    try:
        i = ids.index(current.pk)
    except ValueError:
        return {"prev": None, "next": None}
    return {"prev": items[i - 1] if i > 0 else None, "next": items[i + 1] if i + 1 < len(items) else None}


@register.filter
def strip_num(title):
    """'2. Thêm di tích' -> 'Thêm di tích'"""
    return re.sub(r"^\s*\d+[.)]\s*", "", title or "")


APP_ORDER = ["heritage", "interactions", "dashboard", "core", "auth"]
APP_NAMES = {"auth": "Tài khoản và vai trò", "core": "Hệ thống", "heritage": "Nội dung di tích",
             "interactions": "Tương tác người dùng"}
MODEL_NAMES = {("auth", "User"): "Tài khoản người dùng", ("auth", "Group"): "Vai trò (nhóm quyền)"}


@register.filter
def vd_app_list(app_list):
    """Sắp xếp và đổi tên nhóm chức năng ở trang chủ quản trị cho dễ hiểu (không đổi dữ liệu gốc)."""
    out = []
    for app in app_list or []:
        app = dict(app)
        label = app.get("app_label")
        app["name"] = APP_NAMES.get(label, app.get("name"))
        models = []
        for m in app.get("models", []):
            m = dict(m)
            m["name"] = MODEL_NAMES.get((label, m.get("object_name")), m.get("name"))
            models.append(m)
        app["models"] = models
        out.append(app)
    rank = {a: i for i, a in enumerate(APP_ORDER)}
    return sorted(out, key=lambda a: (rank.get(a.get("app_label"), 99), a.get("name", "")))
