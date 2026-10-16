"""Quản trị tương tác người dùng: đánh giá, góp ý, từ ngữ cấm (TR 5.2, FR-D04, FR-D05)."""
from django import forms
from django.contrib import admin, messages
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.text import Truncator

from .models import AnhGopY, DanhGia, GopY, LichSuXuLy, TrangThaiDuyet, TuCam

NGON_NGU = {"vi": "Tiếng Việt", "en": "English", "zh-hans": "中文"}
TONE_DUYET = {"pending": "dong", "approved": "ngoc", "hidden": "da", "spam": "son"}
TONE_XULY = {"moi": "dong", "dang": "ngoc", "xong": "da", "dong": "da"}
TONE_LOAI = {"xuong_cap": "solid-son", "hoi_dap": "ngoc", "mong_muon": "dong", "dich_vu": "ngoc", "khac": "da"}


def che_email(v):
    if not v or "@" not in v:
        return v or ""
    ten, mien = v.split("@", 1)
    return f"{ten[:2]}***@{mien}"


def che_sdt(v):
    v = (v or "").strip()
    if len(v) <= 4:
        return "***" if v else ""
    return f"{v[:4]}***{v[-3:]}" if len(v) > 7 else f"{v[:2]}***{v[-2:]}"


def ngay(dt):
    return timezone.localtime(dt).strftime("%d/%m/%Y %H:%M") if dt else "—"


def badge(tone, text):
    return format_html('<span class="vd-badge vd-badge-{}">{}</span>', tone, text)


def stars(n):
    n = int(n or 0)
    return format_html('<span class="vd-stars" title="{} sao">{}<span class="off">{}</span></span>', n, "★" * n, "★" * (5 - n))


class NgonNguFilter(admin.SimpleListFilter):
    title = "ngôn ngữ"
    parameter_name = "ngon_ngu"

    def lookups(self, request, model_admin):
        return list(NGON_NGU.items())

    def queryset(self, request, qs):
        return qs.filter(ngon_ngu=self.value()) if self.value() else qs


class ContactMaskMixin:
    """Email / điện thoại hiển thị che bớt với người không phải Quản trị hệ thống. Dùng chung khung danh sách có lời nhắc."""

    @admin.display(description="Ngày gửi", ordering="ngay_tao")
    def ngay_gui(self, obj):
        return ngay(obj.ngay_tao)

    change_list_template = "admin/interactions/change_list.html"

    def get_object(self, request, object_id, from_field=None):
        obj = super().get_object(request, object_id, from_field)
        if obj is not None:
            obj._vd_full_contact = request.user.is_superuser
        return obj

    @admin.display(description="Email")
    def email_hien_thi(self, obj):
        if not obj.email:
            return "—"
        return obj.email if getattr(obj, "_vd_full_contact", False) else che_email(obj.email)

    @admin.display(description="Điện thoại")
    def sdt_hien_thi(self, obj):
        if not obj.dien_thoai:
            return "—"
        return obj.dien_thoai if getattr(obj, "_vd_full_contact", False) else che_sdt(obj.dien_thoai)


# ================================================================ Đánh giá, nhận xét
class DanhGiaForm(forms.ModelForm):
    class Meta:
        model = DanhGia
        fields = ["trang_thai", "phan_hoi"]
        widgets = {"phan_hoi": forms.Textarea(attrs={"rows": 4, "cols": 80})}
        help_texts = {
            "phan_hoi": "Hiển thị công khai ngay dưới nhận xét (khi nhận xét đã được duyệt). Viết lịch sự, ngắn gọn.",
            "trang_thai": "Chỉ nhận xét “Đã duyệt” mới hiển thị trên website.",
        }


@admin.register(DanhGia)
class DanhGiaAdmin(ContactMaskMixin, admin.ModelAdmin):
    form = DanhGiaForm
    list_display = ["sao", "trich_noi_dung", "di_tich", "ten_hien_thi", "trang_thai_mau", "co_spam", "ngay_gui"]
    list_display_links = ["trich_noi_dung"]
    list_filter = ["trang_thai", "nghi_spam", "so_sao", ("di_tich", admin.RelatedOnlyFieldListFilter), NgonNguFilter,
                   "ngay_tao"]
    search_fields = ["noi_dung", "ten_hien_thi", "di_tich__ten", "di_tich__ma", "phan_hoi"]
    date_hierarchy = "ngay_tao"
    list_select_related = ["di_tich"]
    list_per_page = 50
    actions = ["duyet", "an", "danh_dau_spam"]
    readonly_fields = ["di_tich", "sao", "noi_dung", "ten_hien_thi", "email_hien_thi", "sdt_hien_thi", "ngon_ngu_hien_thi",
                       "dong_y", "ngay_tao", "co_spam", "nguoi_duyet", "ngay_duyet"]
    fieldsets = [
        ("Nhận xét", {"fields": ["di_tich", "sao", "noi_dung", "ten_hien_thi", "ngay_tao", "ngon_ngu_hien_thi"]}),
        ("Liên hệ người gửi", {"fields": ["email_hien_thi", "sdt_hien_thi", "dong_y"],
                               "description": "Thông tin cá nhân – chỉ dùng để liên hệ lại, không công khai."}),
        ("Kiểm duyệt", {"fields": ["co_spam", "trang_thai", "phan_hoi", "nguoi_duyet", "ngay_duyet"]}),
    ]

    @admin.display(description="Sao", ordering="so_sao")
    def sao(self, obj):
        return stars(obj.so_sao)

    @admin.display(description="Nhận xét")
    def trich_noi_dung(self, obj):
        return format_html('<span class="vd-excerpt">{}</span>', Truncator(obj.noi_dung).chars(110))

    @admin.display(description="Trạng thái", ordering="trang_thai")
    def trang_thai_mau(self, obj):
        return badge(TONE_DUYET.get(obj.trang_thai, "da"), obj.get_trang_thai_display())

    @admin.display(description="Nghi spam", ordering="nghi_spam")
    def co_spam(self, obj):
        if not obj.nghi_spam:
            return "—"
        return format_html('<span class="vd-flag">⚑ Nghi spam<small>{}</small></span>', obj.ly_do_nghi or "")

    @admin.display(description="Ngôn ngữ")
    def ngon_ngu_hien_thi(self, obj):
        return NGON_NGU.get(obj.ngon_ngu, obj.ngon_ngu)

    def has_add_permission(self, request):
        return False

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        cho = DanhGia.objects.filter(trang_thai=TrangThaiDuyet.PENDING).count()
        try:
            url = reverse("dashboard:moderation")
        except Exception:  # pragma: no cover
            url = None
        if url:
            msg = format_html(
                '<div class="vd-callout"><span>Có <strong>{}</strong> nhận xét chờ duyệt. Trang <em>Kiểm duyệt nhanh</em> '
                "cho phép duyệt từng thẻ bằng phím tắt.</span>"
                '<a class="vd-btn vd-btn-primary" href="{}">Mở Kiểm duyệt nhanh →</a></div>', cho, url)
            extra_context["vd_callout"] = msg
        return super().changelist_view(request, extra_context)

    def save_model(self, request, obj, form, change):
        if "trang_thai" in form.changed_data and obj.trang_thai != TrangThaiDuyet.PENDING:
            obj.nguoi_duyet, obj.ngay_duyet = request.user, timezone.now()
        super().save_model(request, obj, form, change)

    def _set(self, request, qs, tt, label):
        n = 0
        for obj in qs.select_related("di_tich"):
            if obj.trang_thai == tt:
                continue
            obj.trang_thai, obj.nguoi_duyet, obj.ngay_duyet = tt, request.user, timezone.now()
            if tt == TrangThaiDuyet.SPAM:
                obj.nghi_spam = True
            obj.save()  # gọi save() từng bản ghi để nhật ký thao tác ghi nhận
            n += 1
        self.message_user(request, f"{label} {n} nhận xét.", messages.SUCCESS)

    @admin.action(description="Duyệt (hiển thị công khai)", permissions=["change"])
    def duyet(self, request, queryset):
        self._set(request, queryset, TrangThaiDuyet.APPROVED, "Đã duyệt")

    @admin.action(description="Ẩn", permissions=["change"])
    def an(self, request, queryset):
        self._set(request, queryset, TrangThaiDuyet.HIDDEN, "Đã ẩn")

    @admin.action(description="Đánh dấu spam", permissions=["change"])
    def danh_dau_spam(self, request, queryset):
        self._set(request, queryset, TrangThaiDuyet.SPAM, "Đã đánh dấu spam")


# ================================================================ Góp ý
class LichSuInline(admin.TabularInline):
    model = LichSuXuLy
    extra = 0
    can_delete = False
    verbose_name = "Bước xử lý"
    verbose_name_plural = "Lịch sử xử lý"
    fields = ["thoi_gian_col", "nguoi_col", "noi_dung_col"]
    readonly_fields = fields

    @admin.display(description="Thời gian")
    def thoi_gian_col(self, obj):
        return timezone.localtime(obj.thoi_gian).strftime("%H:%M %d/%m/%Y") if obj.thoi_gian else "—"

    @admin.display(description="Người thực hiện")
    def nguoi_col(self, obj):
        return (obj.nguoi.get_full_name() or obj.nguoi.username) if obj.nguoi else "—"

    @admin.display(description="Nội dung")
    def noi_dung_col(self, obj):
        return obj.noi_dung

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class NguoiXuLyChoice(forms.ModelChoiceField):
    def label_from_instance(self, u):
        return u.get_full_name() or u.username


class GopYForm(forms.ModelForm):
    class Meta:
        model = GopY
        fields = ["trang_thai", "nguoi_xu_ly", "ghi_chu_noi_bo", "phan_hoi", "cong_khai"]
        widgets = {"ghi_chu_noi_bo": forms.Textarea(attrs={"rows": 3, "cols": 80}),
                   "phan_hoi": forms.Textarea(attrs={"rows": 5, "cols": 80})}
        help_texts = {
            "trang_thai": "Mới → Đang xử lý → Đã xử lý / Đóng.",
            "nguoi_xu_ly": "Cán bộ chịu trách nhiệm xử lý góp ý này.",
            "ghi_chu_noi_bo": "Chỉ cán bộ quản trị thấy.",
            "phan_hoi": "Người gửi xem được khi tra cứu bằng mã. Nếu chọn “Công khai”, hiển thị trong mục Hỏi đáp.",
            "cong_khai": "Chỉ nên chọn với câu hỏi có ích cho nhiều người và đã có phản hồi.",
        }

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        from django.contrib.auth import get_user_model
        f = self.fields["nguoi_xu_ly"]
        self.fields["nguoi_xu_ly"] = NguoiXuLyChoice(
            queryset=get_user_model().objects.filter(is_staff=True, is_active=True).order_by("username"),
            required=False, label=f.label, help_text=f.help_text, empty_label="— Chưa giao —")

    def clean(self):
        cd = super().clean()
        if cd.get("cong_khai") and not (cd.get("phan_hoi") or "").strip():
            self.add_error("cong_khai", "Cần nhập phản hồi trước khi công khai trong mục Hỏi đáp.")
        return cd


@admin.register(GopY)
class GopYAdmin(ContactMaskMixin, admin.ModelAdmin):
    form = GopYForm
    inlines = [LichSuInline]
    list_display = ["ma_tra_cuu", "loai_mau", "di_tich", "trich_noi_dung", "trang_thai_mau", "nguoi_xu_ly_col",
                    "ngay_gui", "ngay_xu_ly_col", "so_ngay_cho"]
    list_display_links = ["ma_tra_cuu"]
    list_filter = ["loai", "trang_thai", ("nguoi_xu_ly", admin.RelatedOnlyFieldListFilter), "nghi_spam", "cong_khai",
                   "ngay_tao"]
    search_fields = ["ma_tra_cuu", "noi_dung", "ho_ten", "di_tich__ten", "phan_hoi"]
    date_hierarchy = "ngay_tao"
    list_select_related = ["di_tich", "nguoi_xu_ly"]
    list_per_page = 50
    actions = ["nhan_xu_ly", "danh_dau_xong", "dong"]
    readonly_fields = ["ma_tra_cuu", "loai_mau", "di_tich", "noi_dung", "ho_ten", "email_hien_thi", "sdt_hien_thi",
                       "ngon_ngu_hien_thi", "dong_y", "ngay_tao", "anh_dinh_kem", "co_spam", "ngay_xu_ly"]
    fieldsets = [
        ("Nội dung góp ý", {"fields": ["ma_tra_cuu", "loai_mau", "di_tich", "noi_dung", "anh_dinh_kem", "ngay_tao", "co_spam"]}),
        ("Người gửi", {"fields": ["ho_ten", "email_hien_thi", "sdt_hien_thi", "ngon_ngu_hien_thi", "dong_y"],
                       "description": "Thông tin cá nhân – chỉ dùng để liên hệ lại, không công khai."}),
        ("Xử lý", {"fields": ["nguoi_xu_ly", "trang_thai", "ghi_chu_noi_bo", "ngay_xu_ly"]}),
        ("Phản hồi người gửi", {"fields": ["phan_hoi", "cong_khai"]}),
    ]

    @admin.display(description="Ngôn ngữ")
    def ngon_ngu_hien_thi(self, obj):
        return NGON_NGU.get(obj.ngon_ngu, obj.ngon_ngu)

    @admin.display(description="Ngày hoàn thành", ordering="ngay_xu_ly")
    def ngay_xu_ly_col(self, obj):
        return ngay(obj.ngay_xu_ly)

    @admin.display(description="Loại", ordering="loai")
    def loai_mau(self, obj):
        return badge(TONE_LOAI.get(obj.loai, "da"), obj.get_loai_display())

    @admin.display(description="Nội dung")
    def trich_noi_dung(self, obj):
        return format_html('<span class="vd-excerpt">{}</span>', Truncator(obj.noi_dung).chars(100))

    @admin.display(description="Trạng thái", ordering="trang_thai")
    def trang_thai_mau(self, obj):
        return badge(TONE_XULY.get(obj.trang_thai, "da"), obj.get_trang_thai_display())

    @admin.display(description="Người xử lý", ordering="nguoi_xu_ly__username")
    def nguoi_xu_ly_col(self, obj):
        u = obj.nguoi_xu_ly
        return (u.get_full_name() or u.username) if u else format_html('<span class="vd-quiet">Chưa giao</span>')

    @admin.display(description="Chờ (ngày)")
    def so_ngay_cho(self, obj):
        end = obj.ngay_xu_ly if obj.trang_thai in (GopY.XuLy.XONG, GopY.XuLy.DONG) and obj.ngay_xu_ly else None
        if obj.trang_thai in (GopY.XuLy.XONG, GopY.XuLy.DONG):
            return format_html('<span class="vd-quiet">{}</span>', "—" if not end else (end - obj.ngay_tao).days)
        d = (timezone.now() - obj.ngay_tao).days
        cls = "vd-wait-hot" if d >= 7 or obj.loai == GopY.Loai.XUONG_CAP and d >= 2 else ""
        return format_html('<span class="{}">{}</span>', cls, d)

    @admin.display(description="Nghi spam")
    def co_spam(self, obj):
        return format_html('<span class="vd-flag">⚑ Nghi spam</span>') if obj.nghi_spam else "Không"

    @admin.display(description="Ảnh đính kèm")
    def anh_dinh_kem(self, obj):
        imgs = list(obj.anh.all())
        if not imgs:
            return "Không có"
        return format_html('<div class="vd-thumbs">{}</div>', format_html_join(
            "", '<a href="{0}" target="_blank" rel="noopener"><img src="{0}" alt="Ảnh đính kèm {1}" loading="lazy"></a>',
            ((a.tep.url, i) for i, a in enumerate(imgs, 1))))

    def has_add_permission(self, request):
        return False

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        xc = GopY.objects.filter(loai=GopY.Loai.XUONG_CAP, trang_thai__in=[GopY.XuLy.MOI, GopY.XuLy.DANG]).count()
        if xc and request.GET.get("loai__exact") != "xuong_cap":
            extra_context["vd_callout"] = format_html(
                '<div class="vd-callout vd-callout-son"><span><strong>{}</strong> báo di tích xuống cấp chưa xử lý xong.</span>'
                '<a class="vd-btn vd-btn-danger" href="?loai__exact=xuong_cap&amp;trang_thai__in=moi,dang">Xem ngay</a></div>', xc)
        return super().changelist_view(request, extra_context)

    # ---- lịch sử xử lý ----
    @staticmethod
    def _ten(u):
        return (u.get_full_name() or u.username) if u else "chưa giao"

    def save_model(self, request, obj, form, change):
        notes = []
        if change:
            old = GopY.objects.get(pk=obj.pk)
            if old.trang_thai != obj.trang_thai:
                notes.append(f"Trạng thái: {old.get_trang_thai_display()} → {obj.get_trang_thai_display()}")
            if old.nguoi_xu_ly_id != obj.nguoi_xu_ly_id:
                notes.append(f"Người xử lý: {self._ten(old.nguoi_xu_ly)} → {self._ten(obj.nguoi_xu_ly)}")
            if (old.phan_hoi or "").strip() != (obj.phan_hoi or "").strip():
                notes.append("Cập nhật phản hồi cho người gửi" if old.phan_hoi else "Gửi phản hồi cho người gửi")
            if old.cong_khai != obj.cong_khai:
                notes.append("Công khai trong mục Hỏi đáp" if obj.cong_khai else "Bỏ công khai")
            if (old.ghi_chu_noi_bo or "") != (obj.ghi_chu_noi_bo or ""):
                notes.append("Sửa ghi chú nội bộ")
            if obj.trang_thai == GopY.XuLy.DONG and not obj.ngay_xu_ly:
                obj.ngay_xu_ly = timezone.now()
        super().save_model(request, obj, form, change)
        if notes:
            LichSuXuLy.objects.create(gop_y=obj, nguoi=request.user, noi_dung="; ".join(notes)[:500])

    def _bulk(self, request, qs, apply, label):
        n = 0
        for obj in qs.select_related("nguoi_xu_ly"):
            note = apply(obj)
            if note:
                obj.save()
                LichSuXuLy.objects.create(gop_y=obj, nguoi=request.user, noi_dung=note[:500])
                n += 1
        self.message_user(request, f"{label}: {n} góp ý.", messages.SUCCESS)

    @admin.action(description="Nhận xử lý (giao cho tôi)", permissions=["change"])
    def nhan_xu_ly(self, request, queryset):
        def apply(o):
            if o.trang_thai in (GopY.XuLy.XONG, GopY.XuLy.DONG):
                return None
            parts = []
            if o.nguoi_xu_ly_id != request.user.pk:
                parts.append(f"Người xử lý: {self._ten(o.nguoi_xu_ly)} → {self._ten(request.user)}")
                o.nguoi_xu_ly = request.user
            if o.trang_thai == GopY.XuLy.MOI:
                parts.append("Trạng thái: Mới → Đang xử lý")
                o.trang_thai = GopY.XuLy.DANG
            return "; ".join(parts)
        self._bulk(request, queryset, apply, "Đã nhận xử lý")

    @admin.action(description="Đánh dấu đã xử lý", permissions=["change"])
    def danh_dau_xong(self, request, queryset):
        def apply(o):
            if o.trang_thai == GopY.XuLy.XONG:
                return None
            note = f"Trạng thái: {o.get_trang_thai_display()} → Đã xử lý"
            o.trang_thai = GopY.XuLy.XONG
            if not o.nguoi_xu_ly_id:
                o.nguoi_xu_ly = request.user
            return note
        self._bulk(request, queryset, apply, "Đã đánh dấu xử lý xong")

    @admin.action(description="Đóng", permissions=["change"])
    def dong(self, request, queryset):
        def apply(o):
            if o.trang_thai == GopY.XuLy.DONG:
                return None
            note = f"Trạng thái: {o.get_trang_thai_display()} → Đóng"
            o.trang_thai = GopY.XuLy.DONG
            o.ngay_xu_ly = o.ngay_xu_ly or timezone.now()
            return note
        self._bulk(request, queryset, apply, "Đã đóng")


# ================================================================ Từ ngữ cấm
class ThemHangLoatForm(forms.Form):
    danh_sach = forms.CharField(
        label="Danh sách từ / cụm từ", widget=forms.Textarea(attrs={"rows": 14, "cols": 60}),
        help_text="Mỗi dòng một từ hoặc cụm từ (tiếng Việt, tiếng Anh, tiếng Trung). Không phân biệt hoa thường; "
                  "từ đã có sẽ được bỏ qua.")


@admin.register(TuCam)
class TuCamAdmin(admin.ModelAdmin):
    change_list_template = "admin/interactions/change_list.html"
    list_display = ["tu"]
    search_fields = ["tu"]
    ordering = ["tu"]
    list_per_page = 100

    def get_urls(self):
        return [path("them-hang-loat/", self.admin_site.admin_view(self.them_hang_loat), name="interactions_tucam_bulk")] \
            + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        if self.has_add_permission(request):
            extra_context["vd_callout"] = format_html(
                '<div class="vd-callout"><span>Nhận xét, góp ý chứa các từ dưới đây sẽ tự động bị gắn cờ <em>Nghi spam</em>.</span>'
                '<a class="vd-btn vd-btn-primary" href="{}">Thêm nhiều từ cùng lúc</a></div>',
                reverse("admin:interactions_tucam_bulk"))
        return super().changelist_view(request, extra_context)

    def them_hang_loat(self, request):
        if not self.has_add_permission(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        form = ThemHangLoatForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            co_san = {t.lower() for t in TuCam.objects.values_list("tu", flat=True)}
            moi, bo_qua = 0, 0
            for line in form.cleaned_data["danh_sach"].splitlines():
                w = " ".join(line.split())[:100]
                if not w:
                    continue
                if w.lower() in co_san:
                    bo_qua += 1
                    continue
                try:
                    with transaction.atomic():
                        TuCam.objects.create(tu=w)
                    co_san.add(w.lower())
                    moi += 1
                except IntegrityError:
                    bo_qua += 1
            self.message_user(request, f"Đã thêm {moi} từ; bỏ qua {bo_qua} từ trùng.", messages.SUCCESS)
            return redirect("admin:interactions_tucam_changelist")
        ctx = {**self.admin_site.each_context(request), "title": "Thêm từ ngữ cấm hàng loạt", "form": form,
               "opts": self.model._meta}
        return render(request, "admin/interactions/tucam/bulk.html", ctx)
