"""Khu quản trị nội dung di tích (TR 5.3 FR-A03…A11, 5.4 FR-H01, H02, H06) – cho cán bộ không chuyên CNTT.

URL names bổ sung (namespace admin):
    heritage_ditich_wizard           – Thêm di tích (từng bước)          …/heritage/ditich/them-tung-buoc/
    heritage_ditich_import           – Nhập từ Excel (tải lên, xem trước, xác nhận)
    heritage_ditich_import_template  – Tải file mẫu Excel
    heritage_ditich_preview  <id>    – Xem trước trang công khai (kể cả bản nháp)
    heritage_ditich_upload   <id>    – nhận ảnh kéo-thả (XHR, JSON)
    heritage_ditich_images   <id>    – danh sách ảnh (JSON)
    heritage_ditich_image_order  <id>            – lưu thứ tự ảnh (AJAX)
    heritage_ditich_image_avatar <id> <image_id> – đặt ảnh đại diện (AJAX)
    heritage_ditich_image_update <id> <image_id> – sửa chú thích / tác giả / nguồn (AJAX)
    heritage_ditich_image_delete <id> <image_id> – xóa ảnh (AJAX)
    heritage_hinhanh_picker          – thư viện ảnh cho trình soạn thảo (JSON)
"""
import re

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.db.models import Count, F, Q
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from modeltranslation.admin import TranslationAdmin, TranslationStackedInline, TranslationTabularInline

from core.models import SiteConfig
from core.utils import in_van_don

from . import admin_views
from .admin_forms import (DiemDiTichInlineForm, DiTichAdminForm, HinhAnhAdminForm, SortableInlineForm,
                          VideoInlineForm, can_publish, rich_form)
from .images import MIN_RECOMMENDED
from .models import (DiemDiTich, DiemTuyen, DiTich, HinhAnh, KhuVuc, LeHoi, LoaiHinh, NguonThamKhao, ThongTinHuuIch,
                     TinTuc, TrangThai, TrangTinh, TuyenThamQuan, Video)

CSS = "vd-admin/heritage/heritage-admin.css"
COMMON_JS = "vd-admin/heritage/common.js"
COORD_EPS = 0.0002  # trùng tọa độ: sai khác < 0.0002° (~20 m)

TABS = [
    ("chung", "Thông tin chung"),
    ("noidung", "Nội dung"),
    ("vitri", "Vị trí"),
    ("anh", "Ảnh, video"),
    ("thamquan", "Hướng dẫn tham quan"),
    ("en", "Bản dịch EN"),
    ("zh", "Bản dịch 中文"),
    ("seo", "SEO & xuất bản"),
]
TAB_INTRO = {
    "chung": "Các ô có dấu * là bắt buộc. Bấm (?) cạnh tên ô để xem giải thích và ví dụ.",
    "noidung": "Tóm tắt 1–3 câu (bắt buộc) và bài giới thiệu chia mục. Có thể dán từ Word – hệ thống chỉ giữ định dạng cơ bản.",
    "vitri": "Mỗi điểm nhập tọa độ theo một trong 3 cách: dán độ-phút-giây, nhập số thập phân, hoặc bấm trên bản đồ. "
             "Ba cách tự đồng bộ. Di tích nhiều điểm (đình, chùa, giếng…): bấm “Thêm điểm”. Kéo ⠿ để sắp thứ tự.",
    "anh": "Kéo thả nhiều ảnh cùng lúc. Bấm ★ để chọn ảnh đại diện, kéo ảnh để sắp thứ tự. "
           "Chú thích, tác giả, nguồn của từng ảnh được lưu ngay khi rời ô nhập.",
    "thamquan": "Thông tin thực tế cho du khách: cách đi, giờ mở cửa, phí, liên hệ.",
    "en": "Nhập bản tiếng Anh. Ô nào để trống, trang công khai hiện bản tiếng Việt kèm nhãn “Bản dịch đang cập nhật”. "
          "Bấm “Xem bản tiếng Việt” cạnh mỗi ô để đối chiếu.",
    "zh": "Nhập bản tiếng Trung giản thể. Ô nào để trống, trang công khai hiện bản tiếng Việt kèm nhãn "
          "“Bản dịch đang cập nhật”. Bấm “Xem bản tiếng Việt” cạnh mỗi ô để đối chiếu.",
    "seo": "Trạng thái xuất bản và thông tin hiển thị trên Google. Phần SEO không bắt buộc.",
}
WIZARD_STEPS = [
    {"n": 1, "label": "Thông tin", "tabs": "chung"},
    {"n": 2, "label": "Vị trí", "tabs": "vitri"},
    {"n": 3, "label": "Ảnh", "tabs": "anh"},
    {"n": 4, "label": "Nội dung", "tabs": "noidung thamquan"},
    {"n": 5, "label": "Kiểm tra và gửi duyệt", "tabs": "kiemtra"},
]
MISSING_TAB = {"tên tiếng Việt": "chung", "tóm tắt tiếng Việt": "noidung", "ảnh đại diện": "anh",
               "cấp xếp hạng": "chung", "khu vực": "chung"}
TRANSLATED = ("ten", "dia_chi_moi", "tom_tat", "noi_dung", "thong_tin_tham_quan", "gio_mo_cua", "phi_tham_quan",
              "hien_trang_mo_ta")


LANG_SUFFIX = {"vi": "", "en": " (tiếng Anh)", "zh_hans": " (tiếng Trung)"}


class VDTranslationMixin:
    """Nhãn trường dịch dễ đọc: “Tên di tích”, “Tên di tích (tiếng Anh)” thay cho “Tên di tích [en]”."""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        ff = super().formfield_for_dbfield(db_field, request, **kwargs)
        base = getattr(db_field, "translated_field", None)
        lang = getattr(db_field, "language", "")
        if ff is not None and base is not None and lang:
            label = str(base.verbose_name)
            ff.label = label[:1].upper() + label[1:] + LANG_SUFFIX.get(lang.replace("-", "_"), f" ({lang})")
        return ff


class VDAdmin(VDTranslationMixin, TranslationAdmin):
    view_on_site = False


class VDStackedInline(VDTranslationMixin, TranslationStackedInline):
    pass


class VDTabularInline(VDTranslationMixin, TranslationTabularInline):
    pass


def lang_fieldsets(fields, extra=None, extra_title="Thiết lập", collapse_translations=True):
    """Nhóm trường đa ngôn ngữ: Tiếng Việt trước, rồi Tiếng Anh, Tiếng Trung."""
    def tr(lang):
        return tuple(f"{n}_{lang}" for n in fields)
    cls = ("collapse",) if collapse_translations else ()
    fs = [("Tiếng Việt", {"fields": tr("vi"), "classes": ("vdh-lang", "vdh-lang-vi")}),
          ("Tiếng Anh (English) – để trống sẽ hiện bản tiếng Việt", {"fields": tr("en"),
                                                                    "classes": ("vdh-lang", "vdh-lang-en") + cls}),
          ("Tiếng Trung (中文) – để trống sẽ hiện bản tiếng Việt", {"fields": tr("zh_hans"),
                                                                 "classes": ("vdh-lang", "vdh-lang-zh") + cls})]
    if extra:
        fs.append((extra_title, {"fields": extra}))
    return fs


class VDMedia:
    css = {"all": (CSS,)}
    js = (COMMON_JS,)


# =========================================================================== Inline của Di tích
class DiemDiTichInline(VDStackedInline):
    model = DiemDiTich
    form = DiemDiTichInlineForm
    template = "admin/heritage/ditich/diem_inline.html"
    fields = ("ten_vi", "ten_en", "ten_zh_hans", "toa_do", "vi_do", "kinh_do", "do_tin_cay", "diem_chinh",
              "mo_ta_vi", "mo_ta_en", "mo_ta_zh_hans", "thu_tu")
    extra = 0
    verbose_name = "Điểm"
    verbose_name_plural = "Các điểm của di tích"
    vd_tab = "vitri"

    def get_extra(self, request, obj=None, **kw):
        return 1 if obj is None or not obj.diem.exists() else 0


class VideoInline(VDStackedInline):
    model = Video
    form = VideoInlineForm
    fields = (("tieu_de_vi", "tieu_de_en", "tieu_de_zh_hans"), ("youtube_url", "tep"), "nguon", "thu_tu")
    extra = 0
    classes = ("vdh-videos", "vdh-sortable")
    verbose_name = "Video"
    verbose_name_plural = "Video (YouTube hoặc tệp MP4 ≤ 200 MB)"
    vd_tab = "anh"


class NguonThamKhaoInline(admin.TabularInline):
    model = NguonThamKhao
    form = SortableInlineForm
    fields = ("ten", "url", "ngay", "thu_tu")
    extra = 0
    classes = ("vdh-sortable",)
    verbose_name = "Nguồn"
    verbose_name_plural = "Nguồn tham khảo (kéo ⠿ để sắp xếp)"
    vd_tab = "noidung"


# =========================================================================== Bộ lọc
class ToaDoFilter(admin.SimpleListFilter):
    title = "tọa độ"
    parameter_name = "toa_do"

    def lookups(self, request, model_admin):
        return [("thieu", "Thiếu tọa độ"), ("du", "Đủ tọa độ")]

    def queryset(self, request, qs):
        if self.value() == "thieu":
            return qs.filter(Q(n_diem=0) | Q(n_toado__lt=F("n_diem")))
        if self.value() == "du":
            return qs.filter(n_diem__gt=0, n_toado=F("n_diem"))
        return qs


class AnhFilter(admin.SimpleListFilter):
    title = "ảnh"
    parameter_name = "anh"

    def lookups(self, request, model_admin):
        return [("minh_hoa", "Chỉ có ảnh minh họa"), ("khong", "Chưa có ảnh"), ("that", "Đã có ảnh chính thức")]

    def queryset(self, request, qs):
        v = self.value()
        if v == "minh_hoa":
            return qs.filter(n_anh__gt=0, n_anh_that=0)
        if v == "khong":
            return qs.filter(n_anh=0)
        if v == "that":
            return qs.filter(n_anh_that__gt=0)
        return qs


class BanDichFilter(admin.SimpleListFilter):
    title = "bản dịch"
    parameter_name = "ban_dich"

    def lookups(self, request, model_admin):
        return [("thieu", "Thiếu bản dịch EN/ZH"), ("thieu_en", "Thiếu bản dịch EN"),
                ("thieu_zh", "Thiếu bản dịch 中文"), ("du", "Đủ EN và 中文")]

    def queryset(self, request, qs):
        no_en = Q(tom_tat_en__isnull=True) | Q(tom_tat_en="") | Q(ten_en__isnull=True) | Q(ten_en="")
        no_zh = Q(tom_tat_zh_hans__isnull=True) | Q(tom_tat_zh_hans="") | Q(ten_zh_hans__isnull=True) | Q(ten_zh_hans="")
        v = self.value()
        if v == "thieu":
            return qs.filter(no_en | no_zh)
        if v == "thieu_en":
            return qs.filter(no_en)
        if v == "thieu_zh":
            return qs.filter(no_zh)
        if v == "du":
            return qs.exclude(no_en).exclude(no_zh)
        return qs


def completeness_items(obj):
    """Điều kiện xuất bản còn thiếu (đỏ) và gợi ý hoàn thiện (vàng) cho thanh trạng thái đầu form."""
    if not obj or not obj.pk:
        return []
    items = [{"level": "req", "text": f"Thiếu {m}", "tab": MISSING_TAB.get(m, "chung")}
             for m in obj.missing_for_publish()]
    pts = list(obj.diem.all())
    n_coord = sum(1 for p in pts if p.has_coord)
    if not pts:
        items.append({"level": "sug", "text": "Chưa có điểm / tọa độ", "tab": "vitri"})
    elif n_coord < len(pts):
        items.append({"level": "sug", "text": f"Thiếu tọa độ: mới {n_coord}/{len(pts)} điểm có tọa độ", "tab": "vitri"})
    imgs = list(obj.hinh_anh.all())
    real = [h for h in imgs if not h.la_minh_hoa]
    if not imgs:
        items.append({"level": "sug", "text": "Chưa có ảnh", "tab": "anh"})
    elif not real:
        items.append({"level": "sug", "text": "Chỉ có ảnh minh họa tạm – cần ảnh chính thức", "tab": "anh"})
    elif obj.anh_dai_dien_id and obj.anh_dai_dien and obj.anh_dai_dien.la_minh_hoa:
        items.append({"level": "sug", "text": "Ảnh đại diện đang là ảnh minh họa – hãy chọn ảnh chính thức", "tab": "anh"})
    small = [h for h in real if h.rong and h.rong < MIN_RECOMMENDED]
    if small:
        items.append({"level": "sug", "text": f"{len(small)} ảnh nhỏ hơn {MIN_RECOMMENDED} px chiều ngang", "tab": "anh"})
    if not (obj.noi_dung_vi or "").strip():
        items.append({"level": "sug", "text": "Chưa có bài giới thiệu", "tab": "noidung"})
    if obj.tham_quan_duoc and not (obj.thong_tin_tham_quan_vi or "").strip():
        items.append({"level": "sug", "text": "Chưa có hướng dẫn tham quan", "tab": "thamquan"})
    if not (obj.ten_en and obj.tom_tat_en):
        items.append({"level": "sug", "text": "Thiếu bản dịch tiếng Anh (tên, tóm tắt)", "tab": "en"})
    if not (obj.ten_zh_hans and obj.tom_tat_zh_hans):
        items.append({"level": "sug", "text": "Thiếu bản dịch tiếng Trung (tên, tóm tắt)", "tab": "zh"})
    return items


# =========================================================================== Di tích
@admin.register(DiTich)
class DiTichAdmin(VDAdmin):
    form = DiTichAdminForm
    inlines = [DiemDiTichInline, VideoInline, NguonThamKhaoInline]
    change_form_template = "admin/heritage/ditich/change_form.html"
    change_list_template = "admin/heritage/ditich/change_list.html"
    object_history_template = "admin/heritage/ditich/object_history.html"
    list_display = ("ma_hien_thi", "anh_nho", "ten_hien_thi", "cap_hien_thi", "khu_vuc_hien_thi", "trang_thai_hien_thi",
                    "hoan_thien", "luot_xem_hien_thi", "ngay_sua_hien_thi")
    list_display_links = ("ma_hien_thi", "ten_hien_thi")
    list_filter = ("cap_xep_hang", "khu_vuc", "trang_thai", "tham_quan_duoc", ToaDoFilter, AnhFilter, BanDichFilter,
                   "loai_hinh")
    search_fields = ("ma", "ten_vi", "ten_en", "ten_zh_hans", "ten_khac", "search_text")
    list_per_page = 50
    actions = ["gui_duyet", "xuat_ban", "an_di_tich", "xuat_excel"]
    save_on_top = False
    fieldsets = [
        ("Định danh", {"fields": ("ma", "ten_vi", "ten_khac"), "classes": ("vdtab-chung",)}),
        ("Xếp hạng, loại hình", {"fields": ("cap_xep_hang", "loai_hinh", ("so_quyet_dinh", "nam_xep_hang"),
                                            "co_quan_qd"), "classes": ("vdtab-chung",)}),
        ("Địa điểm", {"fields": ("khu_vuc", "khu_vuc_phu", "dia_chi_moi_vi", "dia_chi_cu", "dien_tich"),
                      "classes": ("vdtab-chung",)}),
        ("Hiện trạng", {"fields": (("hien_trang", "tham_quan_duoc"), "hien_trang_mo_ta_vi"),
                        "classes": ("vdtab-chung",)}),
        ("Tóm tắt và bài giới thiệu", {"fields": ("tom_tat_vi", "noi_dung_vi"), "classes": ("vdtab-noidung",)}),
        ("Ảnh đại diện", {"fields": ("anh_dai_dien",), "classes": ("vdtab-anh", "vdh-avatar-fieldset")}),
        ("Thông tin cho du khách", {"fields": ("thong_tin_tham_quan_vi", ("gio_mo_cua_vi", "phi_tham_quan_vi"),
                                               "lien_he"), "classes": ("vdtab-thamquan",)}),
        ("Bản tiếng Anh (English)", {"fields": tuple(f"{f}_en" for f in TRANSLATED),
                                     "classes": ("vdtab-en", "vdh-translation")}),
        ("Bản tiếng Trung (中文)", {"fields": tuple(f"{f}_zh_hans" for f in TRANSLATED),
                                    "classes": ("vdtab-zh", "vdh-translation")}),
        ("Xuất bản", {"fields": ("trang_thai", ("noi_bat", "thu_tu"), "slug"), "classes": ("vdtab-seo",)}),
        ("SEO – Tiếng Việt", {"fields": ("seo_title_vi", "seo_description_vi"), "classes": ("vdtab-seo",)}),
        ("SEO – Tiếng Anh", {"fields": ("seo_title_en", "seo_description_en"), "classes": ("vdtab-seo", "vdh-translation")}),
        ("SEO – Tiếng Trung", {"fields": ("seo_title_zh_hans", "seo_description_zh_hans"),
                               "classes": ("vdtab-seo", "vdh-translation")}),
    ]

    class Media:
        css = {"all": ("vendor/leaflet/leaflet.css", "vendor/quill/quill.snow.css", CSS)}
        js = (COMMON_JS, "vendor/leaflet/leaflet.js", "vd-admin/heritage/ditich-form.js",
              "vd-admin/heritage/coords.js", "vd-admin/heritage/gallery.js")

    # ---------------- danh sách
    def get_queryset(self, request):
        return super().get_queryset(request).select_related("khu_vuc", "anh_dai_dien").annotate(
            n_anh=Count("hinh_anh", distinct=True),
            n_anh_that=Count("hinh_anh", filter=Q(hinh_anh__la_minh_hoa=False), distinct=True),
            n_diem=Count("diem", distinct=True),
            n_toado=Count("diem", filter=Q(diem__vi_do__isnull=False, diem__kinh_do__isnull=False), distinct=True),
        )

    @admin.display(description="Ảnh")
    def anh_nho(self, obj):
        h = obj.anh_dai_dien
        if not h:
            return format_html('<span class="vdh-thumb vdh-thumb-empty" title="Chưa có ảnh đại diện">—</span>')
        return format_html('<img src="{}" alt="" class="vdh-thumb{}" loading="lazy" title="{}">', h.url(480),
                           " vdh-thumb-ph" if h.la_minh_hoa else "",
                           "Ảnh minh họa tạm" if h.la_minh_hoa else "Ảnh đại diện")

    @admin.display(description="Tên di tích", ordering="ten_vi")
    def ten_hien_thi(self, obj):
        if obj.ten_khac:
            khac = obj.ten_khac if len(obj.ten_khac) <= 60 else obj.ten_khac[:58] + "…"
            return format_html('{}<small class="vdh-sub">{}</small>', obj.ten_vi or obj.ten, khac)
        return obj.ten_vi or obj.ten

    @admin.display(description="Mã", ordering="ma")
    def ma_hien_thi(self, obj):
        return obj.ma

    @admin.display(description="Khu vực", ordering="khu_vuc__thu_tu")
    def khu_vuc_hien_thi(self, obj):
        return obj.khu_vuc.ten_vi or obj.khu_vuc.ten

    @admin.display(description="Lượt xem", ordering="luot_xem")
    def luot_xem_hien_thi(self, obj):
        return f"{obj.luot_xem:,}".replace(",", ".")

    @admin.display(description="Ngày sửa", ordering="ngay_sua")
    def ngay_sua_hien_thi(self, obj):
        return format_html('<span title="{}">{}</span>', timezone.localtime(obj.ngay_sua).strftime("%H:%M %d/%m/%Y"),
                           timezone.localtime(obj.ngay_sua).strftime("%d/%m/%Y"))

    @admin.display(description="Cấp", ordering="cap_xep_hang")
    def cap_hien_thi(self, obj):
        return format_html('<span class="vdh-cap vdh-cap-{}">{}</span>', obj.cap_xep_hang,
                           obj.get_cap_xep_hang_display())

    @admin.display(description="Trạng thái", ordering="trang_thai")
    def trang_thai_hien_thi(self, obj):
        return format_html('<span class="vdh-st vdh-st-{}">{}</span>', obj.trang_thai, obj.get_trang_thai_display())

    @admin.display(description="Hoàn thiện")
    def hoan_thien(self, obj):
        chips = []
        n_anh, n_that = getattr(obj, "n_anh", 0), getattr(obj, "n_anh_that", 0)
        if n_anh == 0:
            chips.append(("bad", "Ảnh 0", "Chưa có ảnh nào"))
        elif n_that == 0:
            chips.append(("warn", f"⚠ Ảnh {n_anh}", "Chỉ có ảnh minh họa tạm – cần ảnh chính thức"))
        else:
            chips.append(("ok", f"Ảnh {n_that}", f"{n_that} ảnh chính thức, {n_anh - n_that} ảnh minh họa"))
        n_diem, n_td = getattr(obj, "n_diem", 0), getattr(obj, "n_toado", 0)
        kind = "ok" if n_diem and n_td == n_diem else ("bad" if n_td == 0 else "warn")
        chips.append((kind, f"Tọa độ {n_td}/{n_diem}", "Số điểm có tọa độ / tổng số điểm"))
        en = bool(obj.tom_tat_en and obj.ten_en)
        zh = bool(obj.tom_tat_zh_hans and obj.ten_zh_hans)
        chips.append(("ok" if en else "warn", "EN ✓" if en else "EN ✗", "Bản dịch tiếng Anh (tên, tóm tắt)"))
        chips.append(("ok" if zh else "warn", "中 ✓" if zh else "中 ✗", "Bản dịch tiếng Trung (tên, tóm tắt)"))
        bai = bool((obj.noi_dung_vi or "").strip())
        chips.append(("ok" if bai else "warn", "Bài ✓" if bai else "Bài ✗", "Bài giới thiệu tiếng Việt"))
        return format_html('<span class="vdh-chips">{}</span>', format_html_join(
            "", '<span class="vdh-chip vdh-chip-{}" title="{}">{}</span>', ((k, t, label) for k, label, t in chips)))

    # ---------------- quyền và thao tác hàng loạt
    def has_publish_permission(self, request):
        return can_publish(request.user)

    @admin.action(description="Gửi duyệt các di tích đã chọn", permissions=["change"])
    def gui_duyet(self, request, queryset):
        n = 0
        for obj in queryset.filter(trang_thai=TrangThai.DRAFT):
            obj.trang_thai = TrangThai.REVIEW
            obj.nguoi_sua = request.user
            obj.save()
            n += 1
        if n:
            self.message_user(request, f"Đã gửi duyệt {n} di tích.", messages.SUCCESS)
        else:
            self.message_user(request, "Không có di tích ở trạng thái Nháp trong các mục đã chọn.", messages.WARNING)

    @admin.action(description="Xuất bản các di tích đã chọn", permissions=["publish"])
    def xuat_ban(self, request, queryset):
        ok, bad = 0, []
        for obj in queryset:
            if obj.trang_thai == TrangThai.PUBLISHED:
                continue
            miss = obj.missing_for_publish()
            if miss:
                bad.append(f"{obj.ma} ({', '.join(miss)})")
                continue
            obj.trang_thai = TrangThai.PUBLISHED
            obj.nguoi_sua = request.user
            obj.save()
            ok += 1
        if ok:
            self.message_user(request, f"Đã xuất bản {ok} di tích.", messages.SUCCESS)
        if bad:
            self.message_user(request, f"Bỏ qua {len(bad)} di tích chưa đủ điều kiện – còn thiếu: " + "; ".join(bad[:20])
                              + ("…" if len(bad) > 20 else ""), messages.WARNING)
        if not ok and not bad:
            self.message_user(request, "Các di tích đã chọn đều đã xuất bản.", messages.INFO)

    @admin.action(description="Ẩn các di tích đã chọn khỏi website", permissions=["publish"])
    def an_di_tich(self, request, queryset):
        n = 0
        for obj in queryset.exclude(trang_thai=TrangThai.HIDDEN):
            obj.trang_thai = TrangThai.HIDDEN
            obj.nguoi_sua = request.user
            obj.save()
            n += 1
        self.message_user(request, f"Đã ẩn {n} di tích.", messages.SUCCESS)

    @admin.action(description="Xuất danh sách đã chọn ra Excel (định dạng nhập lại được)", permissions=["view"])
    def xuat_excel(self, request, queryset):
        return admin_views.export_excel(request, queryset)

    # ---------------- URL bổ sung
    def get_urls(self):
        def w(view):
            return self.admin_site.admin_view(lambda request, *a, **k: view(request, self, *a, **k))
        extra = [
            path("them-tung-buoc/", w(admin_views.wizard), name="heritage_ditich_wizard"),
            path("nhap-excel/", w(admin_views.import_upload), name="heritage_ditich_import"),
            path("nhap-excel/tai-mau/", w(admin_views.import_template), name="heritage_ditich_import_template"),
            path("<int:object_id>/xem-truoc/", w(admin_views.preview), name="heritage_ditich_preview"),
            path("<int:object_id>/anh/", w(admin_views.image_list), name="heritage_ditich_images"),
            path("<int:object_id>/anh/tai-len/", w(admin_views.upload_image), name="heritage_ditich_upload"),
            path("<int:object_id>/anh/thu-tu/", w(admin_views.image_order), name="heritage_ditich_image_order"),
            path("<int:object_id>/anh/<int:image_id>/dai-dien/", w(admin_views.image_set_avatar),
                 name="heritage_ditich_image_avatar"),
            path("<int:object_id>/anh/<int:image_id>/sua/", w(admin_views.image_update),
                 name="heritage_ditich_image_update"),
            path("<int:object_id>/anh/<int:image_id>/xoa/", w(admin_views.image_delete),
                 name="heritage_ditich_image_delete"),
        ]
        return extra + super().get_urls()

    # ---------------- biểu mẫu
    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)
        form.request_user = request.user
        return form

    def get_changeform_initial_data(self, request):
        data = super().get_changeform_initial_data(request)
        data.setdefault("trang_thai", TrangThai.DRAFT)
        return data

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        wizard = request.GET.get("wizard") == "1"
        cfg = SiteConfig.get()
        PH = 987654321
        urls = {}
        if obj and obj.pk:
            urls = {
                "upload": reverse("admin:heritage_ditich_upload", args=[obj.pk]),
                "order": reverse("admin:heritage_ditich_image_order", args=[obj.pk]),
                "list": reverse("admin:heritage_ditich_images", args=[obj.pk]),
                "avatar": reverse("admin:heritage_ditich_image_avatar", args=[obj.pk, PH]),
                "update": reverse("admin:heritage_ditich_image_update", args=[obj.pk, PH]),
                "delete": reverse("admin:heritage_ditich_image_delete", args=[obj.pk, PH]),
                "placeholder": str(PH),
            }
        user = request.user
        items = completeness_items(obj)
        context.update({
            "vd_tabs": [{"id": t, "label": label, "intro": TAB_INTRO.get(t, "")} for t, label in TABS],
            "vd_wizard": wizard,
            "vd_steps": WIZARD_STEPS,
            "vd_map_config": {
                "key": cfg.maps_key or "",
                "bounds": settings.VANDON_BOUNDS,
                "center": [20.95, 107.45],
                "esri": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                "osm": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                "nominatim": "https://nominatim.openstreetmap.org/search",
            },
            "vd_gallery": {
                "urls": urls, "items": admin_views.gallery_data(obj),
                "can_upload": bool(obj and obj.pk) and user.has_perm("heritage.add_hinhanh"),
                "can_edit": user.has_perm("heritage.change_hinhanh") and user.has_perm("heritage.change_ditich"),
                "can_delete": user.has_perm("heritage.delete_hinhanh"),
                "min_width": MIN_RECOMMENDED,
            },
            "vd_min_width": MIN_RECOMMENDED,
            "vd_can_upload": bool(obj and obj.pk) and user.has_perm("heritage.add_hinhanh"),
            "vd_completeness": items,
            "vd_missing": obj.missing_for_publish() if obj and obj.pk else [],
            "vd_req_count": len([i for i in items if i["level"] == "req"]),
            "vd_can_publish": can_publish(user),
            "vd_preview_url": reverse("admin:heritage_ditich_preview", args=[obj.pk]) if obj and obj.pk else "",
            "vd_public_url": obj.get_absolute_url() if obj and obj.pk and obj.slug
                             and obj.trang_thai == TrangThai.PUBLISHED else "",
            "vd_modified": int(obj.ngay_sua.timestamp() * 1000) if obj and obj.pk and obj.ngay_sua else 0,
            "vd_real_images": obj.hinh_anh.filter(la_minh_hoa=False).count() if obj and obj.pk else 0,
        })
        resp = super().render_change_form(request, context, add, change, form_url, obj)
        return admin_views.with_extra_csp(resp)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.nguoi_tao = request.user
        obj.nguoi_sua = request.user
        if "_vd_send_review" in request.POST and obj.trang_thai in (TrangThai.DRAFT, TrangThai.REVIEW):
            obj.trang_thai = TrangThai.REVIEW
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        if formset.model is DiemDiTich:
            self._warn_coords(request, form.instance)

    def _warn_coords(self, request, obj):
        for p in obj.diem.all():
            if not p.has_coord:
                continue
            lat, lng = float(p.vi_do), float(p.kinh_do)
            name = p.ten_vi or p.ten
            if not in_van_don(lat, lng):
                messages.warning(request, f"Điểm “{name}” ({lat}, {lng}) nằm ngoài phạm vi Vân Đồn – "
                                          "hãy kiểm tra lại tọa độ (có thể nhầm vĩ độ / kinh độ).")
            dup = (DiemDiTich.objects.exclude(di_tich=obj).select_related("di_tich")
                   .filter(vi_do__gt=lat - COORD_EPS, vi_do__lt=lat + COORD_EPS,
                           kinh_do__gt=lng - COORD_EPS, kinh_do__lt=lng + COORD_EPS))
            for d in dup[:3]:
                messages.warning(request, f"Điểm “{name}” trùng tọa độ với điểm “{d.ten_vi or d.ten}” của di tích "
                                          f"{d.di_tich.ma} – {d.di_tich.ten_vi}. Hãy xác minh lại.")

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        obj = form.instance
        if "_vd_send_review" in request.POST:
            miss = obj.missing_for_publish()
            if miss:
                messages.warning(request, "Đã gửi duyệt. Lưu ý còn thiếu: " + ", ".join(miss) +
                                 " – người duyệt chưa thể xuất bản khi chưa bổ sung.")
            else:
                messages.success(request, f"Đã gửi duyệt “{obj.ten_vi}”. Người có quyền Duyệt nội dung sẽ xuất bản.")

    def _vd_redirect(self, request, obj, response):
        if not isinstance(response, HttpResponseRedirect) or "_popup" in request.POST:
            return response
        if "_vd_send_review" in request.POST:
            return HttpResponseRedirect(reverse("admin:heritage_ditich_changelist"))
        step = request.POST.get("_vd_wizard", "")
        if step.isdigit() and request.GET.get("wizard") == "1":
            return HttpResponseRedirect(
                reverse("admin:heritage_ditich_change", args=[obj.pk]) + f"?wizard=1#step={min(int(step), 5)}")
        tab = request.POST.get("_vd_tab", "")
        if "_vd_draft" in request.POST:
            tab = tab if re.fullmatch(r"[a-z]{2,12}", tab or "") else "anh"
            return HttpResponseRedirect(reverse("admin:heritage_ditich_change", args=[obj.pk]) + "#tab=" + tab)
        if "_continue" in request.POST and re.fullmatch(r"[a-z]{2,12}", tab or ""):
            response["Location"] = response["Location"].split("#")[0] + "#tab=" + tab
        return response

    def response_add(self, request, obj, post_url_continue=None):
        return self._vd_redirect(request, obj, super().response_add(request, obj, post_url_continue))

    def response_change(self, request, obj):
        return self._vd_redirect(request, obj, super().response_change(request, obj))

    # ---------------- lịch sử chỉnh sửa (FR-A11): kèm chi tiết thay đổi từ nhật ký thao tác
    def history_view(self, request, object_id, extra_context=None):
        from core.models import AuditLog
        labels = {f.attname: str(f.verbose_name) for f in DiTich._meta.concrete_fields}
        entries = []
        for e in AuditLog.objects.filter(object_type=DiTich._meta.verbose_name, object_id=str(object_id))[:100]:
            changes = []
            if isinstance(e.changes, dict):
                for k, v in e.changes.items():
                    if isinstance(v, (list, tuple)) and len(v) == 2:
                        changes.append({"field": labels.get(k, k), "old": v[0], "new": v[1]})
            entries.append({"log": e, "changes": changes})
        extra_context = {**(extra_context or {}), "vd_audit": entries}
        return super().history_view(request, object_id, extra_context)


# =========================================================================== Thư viện ảnh
@admin.register(HinhAnh)
class HinhAnhAdmin(VDAdmin):
    form = HinhAnhAdminForm
    change_list_template = "admin/heritage/hinhanh/change_list.html"
    list_display = ("anh_nho", "chu_thich_hien_thi", "di_tich", "nguon", "kich_thuoc", "la_minh_hoa")
    list_display_links = ("anh_nho", "chu_thich_hien_thi")
    list_filter = ("la_minh_hoa", ("di_tich", admin.RelatedOnlyFieldListFilter))
    search_fields = ("chu_thich_vi", "nguon", "tac_gia", "di_tich__ma", "di_tich__ten_vi")
    autocomplete_fields = ("di_tich",)
    readonly_fields = ("xem_anh", "kich_thuoc", "la_minh_hoa")
    list_per_page = 60
    fieldsets = [
        ("Tệp ảnh", {"fields": ("xem_anh", "tep", "kich_thuoc", "la_minh_hoa"),
                     "description": "Chuẩn ảnh: chiều ngang ≥ 1.920 px (ảnh bìa ≥ 2.400 px), tỉ lệ 3:2 hoặc 16:9; "
                                    "rõ nét, không chèn chữ, không logo đơn vị khác; JPG, PNG, WebP, HEIC; tối đa 25 MB. "
                                    "Hệ thống tự xoay, xóa GPS, tạo các cỡ WebP. Tải nhiều ảnh: mở di tích → thẻ Ảnh, video."}),
        ("Thuộc di tích", {"fields": ("di_tich", "diem", "thu_tu")}),
        ("Chú thích và bản quyền", {"fields": ("chu_thich_vi", "chu_thich_en", "chu_thich_zh_hans", "tac_gia",
                                                "nguon", "ngay_chup")}),
    ]
    Media = VDMedia

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("di_tich")

    @admin.display(description="Ảnh")
    def anh_nho(self, obj):
        return format_html('<img src="{}" alt="" class="vdh-thumb" loading="lazy">', obj.url(480))

    @admin.display(description="Xem ảnh")
    def xem_anh(self, obj):
        if not obj or not obj.pk:
            return "—"
        return format_html('<img src="{}" alt="" class="vdh-preview-img">', obj.url(960))

    @admin.display(description="Chú thích", ordering="chu_thich_vi")
    def chu_thich_hien_thi(self, obj):
        return obj.chu_thich_vi or "—"

    @admin.display(description="Kích thước")
    def kich_thuoc(self, obj):
        if not obj or not obj.rong:
            return "—"
        warn = " (nhỏ hơn khuyến nghị)" if obj.rong < MIN_RECOMMENDED else ""
        return f"{obj.rong} × {obj.cao} px{warn}"

    def get_urls(self):
        w = self.admin_site.admin_view
        return [path("chon-anh.json", w(lambda r: admin_views.image_picker(r, self)),
                     name="heritage_hinhanh_picker")] + super().get_urls()

    def save_model(self, request, obj, form, change):
        old = {}
        if change and "tep" in form.changed_data:
            old = dict(obj.bien_the or {})
            obj.bien_the = {}  # yêu cầu signal xử lý lại ảnh mới
        if "tep" in form.changed_data:
            obj.la_minh_hoa = False
        super().save_model(request, obj, form, change)
        storage = obj.tep.storage
        for p in old.values():
            try:
                storage.delete(p)
            except Exception:
                pass
        for w_ in getattr(obj, "_warnings", []) or []:
            messages.warning(request, w_)


# =========================================================================== Danh mục
@admin.register(KhuVuc)
class KhuVucAdmin(VDAdmin):
    list_display = ("ten_hien_thi", "dao", "la_dao", "so_di_tich", "thu_tu")
    list_display_links = ("ten_hien_thi",)
    list_editable = ("thu_tu",)
    prepopulated_fields = {"slug": ("ten_vi",)}
    fieldsets = lang_fieldsets(("ten", "dao"), extra=("slug", "la_dao", "thu_tu"), collapse_translations=False)
    Media = VDMedia

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_n=Count("di_tich"))

    @admin.display(description="Khu vực", ordering="ten_vi")
    def ten_hien_thi(self, obj):
        return obj.ten_vi or obj.ten

    @admin.display(description="Số di tích", ordering="_n")
    def so_di_tich(self, obj):
        return obj._n


@admin.register(LoaiHinh)
class LoaiHinhAdmin(VDAdmin):
    list_display = ("ten_hien_thi", "slug", "thu_tu")
    list_display_links = ("ten_hien_thi",)
    list_editable = ("thu_tu",)
    prepopulated_fields = {"slug": ("ten_vi",)}
    fieldsets = lang_fieldsets(("ten",), extra=("slug", "thu_tu"), collapse_translations=False)
    Media = VDMedia

    @admin.display(description="Loại hình", ordering="ten_vi")
    def ten_hien_thi(self, obj):
        return obj.ten_vi or obj.ten


# =========================================================================== Tuyến tham quan
class DiemTuyenInline(VDTabularInline):
    model = DiemTuyen
    form = SortableInlineForm
    fields = ("di_tich", "ghi_chu_vi", "ghi_chu_en", "ghi_chu_zh_hans", "thu_tu")
    autocomplete_fields = ("di_tich",)
    extra = 1
    classes = ("vdh-sortable",)
    verbose_name = "Điểm dừng"
    verbose_name_plural = "Các điểm dừng (kéo ⠿ để sắp thứ tự)"


@admin.register(TuyenThamQuan)
class TuyenThamQuanAdmin(VDAdmin):
    form = rich_form(TuyenThamQuan, ["mo_ta"])
    list_display = ("ten_hien_thi", "thoi_luong", "so_diem", "trang_thai", "thu_tu")
    list_display_links = ("ten_hien_thi",)
    list_editable = ("thu_tu",)
    list_filter = ("trang_thai",)
    search_fields = ("ten_vi", "ten_en")
    inlines = [DiemTuyenInline]
    autocomplete_fields = ("anh_bia",)
    fieldsets = lang_fieldsets(("ten", "mo_ta", "thoi_luong", "phuong_tien"),
                               extra=("slug", "anh_bia", "thu_tu", "trang_thai"))
    Media = VDMedia

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_n=Count("diem_tuyen"))

    @admin.display(description="Tên tuyến", ordering="ten_vi")
    def ten_hien_thi(self, obj):
        return obj.ten_vi or obj.ten

    @admin.display(description="Số điểm dừng", ordering="_n")
    def so_diem(self, obj):
        return obj._n


# =========================================================================== Lễ hội
@admin.register(LeHoi)
class LeHoiAdmin(VDAdmin):
    form = rich_form(LeHoi, ["mo_ta"])
    list_display = ("ten_hien_thi", "thoi_gian_am_lich", "thang_sap_xep", "trang_thai")
    list_display_links = ("ten_hien_thi",)
    list_filter = ("trang_thai", "thang_sap_xep")
    search_fields = ("ten_vi", "ten_en")
    filter_horizontal = ("di_tich",)
    autocomplete_fields = ("anh",)
    fieldsets = lang_fieldsets(("ten", "mo_ta", "thoi_gian_am_lich", "thoi_gian_duong_lich", "dia_diem", "cong_nhan"),
                               extra=("slug", "thang_sap_xep", "di_tich", "anh", "nguon", "trang_thai"))
    Media = VDMedia

    @admin.display(description="Lễ hội, sự kiện", ordering="ten_vi")
    def ten_hien_thi(self, obj):
        return obj.ten_vi or obj.ten


# =========================================================================== Thông tin hữu ích
@admin.register(ThongTinHuuIch)
class ThongTinHuuIchAdmin(VDAdmin):
    form = rich_form(ThongTinHuuIch, ["noi_dung"])
    list_display = ("tieu_de_hien_thi", "nhom", "cap_nhat", "trang_thai", "thu_tu")
    list_display_links = ("tieu_de_hien_thi",)
    list_editable = ("thu_tu",)
    list_filter = ("nhom", "trang_thai")
    search_fields = ("tieu_de_vi", "tieu_de_en")
    ordering = ("nhom", "thu_tu")
    fieldsets = [("Ngày cập nhật (hiện công khai cho du khách)", {
        "fields": ("ngay_cap_nhat",), "classes": ("vdh-updated-box",),
        "description": "Mỗi khi kiểm tra lại thông tin (giá vé tàu, số điện thoại…), hãy đổi ngày này thành hôm nay."})
    ] + lang_fieldsets(("tieu_de", "noi_dung"), extra=("nhom", "lien_ket", "nguon", "thu_tu", "trang_thai"))
    Media = VDMedia

    @admin.display(description="Tiêu đề", ordering="tieu_de_vi")
    def tieu_de_hien_thi(self, obj):
        return obj.tieu_de_vi or obj.tieu_de

    @admin.display(description="Ngày cập nhật", ordering="ngay_cap_nhat")
    def cap_nhat(self, obj):
        d = obj.ngay_cap_nhat
        if not d:
            return "—"
        age = (timezone.localdate() - d).days
        kind = "ok" if age <= 90 else ("warn" if age <= 180 else "bad")
        title = f"Cập nhật cách đây {age} ngày" + (" – nên kiểm tra lại" if age > 90 else "")
        return format_html('<span class="vdh-date vdh-date-{}" title="{}">{}</span>', kind, title, d.strftime("%d/%m/%Y"))


# =========================================================================== Tin tức, trang tĩnh
@admin.register(TinTuc)
class TinTucAdmin(VDAdmin):
    form = rich_form(TinTuc, ["noi_dung"])
    list_display = ("tieu_de_hien_thi", "ngay_dang", "trang_thai")
    list_display_links = ("tieu_de_hien_thi",)
    list_filter = ("trang_thai",)
    search_fields = ("tieu_de_vi", "tieu_de_en")
    date_hierarchy = "ngay_dang"
    autocomplete_fields = ("anh",)
    fieldsets = lang_fieldsets(("tieu_de", "tom_tat", "noi_dung"), extra=("slug", "anh", "ngay_dang", "trang_thai"))
    Media = VDMedia

    @admin.display(description="Tiêu đề", ordering="tieu_de_vi")
    def tieu_de_hien_thi(self, obj):
        return obj.tieu_de_vi or obj.tieu_de


@admin.register(TrangTinh)
class TrangTinhAdmin(VDAdmin):
    form = rich_form(TrangTinh, ["noi_dung"])
    list_display = ("tieu_de_hien_thi", "slug")
    list_display_links = ("tieu_de_hien_thi",)
    fieldsets = lang_fieldsets(("tieu_de", "noi_dung"), extra=("slug",))
    Media = VDMedia

    @admin.display(description="Tiêu đề", ordering="tieu_de_vi")
    def tieu_de_hien_thi(self, obj):
        return obj.tieu_de_vi or obj.tieu_de


# =========================================================================== Video
@admin.register(Video)
class VideoAdmin(VDAdmin):
    form = VideoInlineForm
    list_display = ("tieu_de_hien_thi", "di_tich", "loai", "nguon", "thu_tu")
    list_display_links = ("tieu_de_hien_thi",)
    list_filter = (("di_tich", admin.RelatedOnlyFieldListFilter),)
    search_fields = ("tieu_de_vi", "di_tich__ma", "di_tich__ten_vi")
    autocomplete_fields = ("di_tich",)
    fieldsets = lang_fieldsets(("tieu_de",), extra=("di_tich", "youtube_url", "tep", "nguon", "thu_tu"))
    Media = VDMedia

    @admin.display(description="Tiêu đề", ordering="tieu_de_vi")
    def tieu_de_hien_thi(self, obj):
        return obj.tieu_de_vi or obj.tieu_de

    @admin.display(description="Loại")
    def loai(self, obj):
        return "YouTube" if obj.youtube_url else "Tệp MP4"

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "thu_tu" in form.base_fields:
            form.base_fields["thu_tu"].widget = forms.NumberInput()
        return form
