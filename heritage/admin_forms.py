"""Biểu mẫu cho khu quản trị nội dung di tích (TR 5.3, 5.4).

- DiTichAdminForm: giới hạn trạng thái theo quyền, kiểm tra điều kiện xuất bản, ảnh đại diện chỉ lấy ảnh
  của chính di tích, trình soạn thảo trực quan, trợ giúp (?) cho từng trường (FR-H01).
- DiemDiTichInlineForm: ô "Tọa độ" nhận DMS hoặc thập phân (kiểm tra lại bằng core.utils.parse_coordinates).
- VideoInlineForm, HinhAnhAdminForm: kiểm tra định dạng, dung lượng.
- ImportUploadForm: tải file Excel.
"""
import os
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.urls import NoReverseMatch, reverse

from core.utils import CoordinateError, parse_coordinates

from .models import DiemDiTich, DiTich, HinhAnh, TrangThai, Video
from .widgets import RichTextWidget

LANGS = ("vi", "en", "zh_hans")
LANG_LABEL = {"vi": "tiếng Việt", "en": "tiếng Anh", "zh_hans": "tiếng Trung"}
PUBLISH_ONLY = {TrangThai.PUBLISHED, TrangThai.HIDDEN}
MAX_IMAGE = 25 * 1024 * 1024
MAX_VIDEO = 200 * 1024 * 1024
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "HEIF", "HEIC", "MPO"}


def can_publish(user):
    return bool(user and user.is_active and (user.is_superuser or user.has_perm("heritage.publish_ditich")))


def picker_url(di_tich_id=None):
    try:
        url = reverse("admin:heritage_hinhanh_picker")
    except NoReverseMatch:  # pragma: no cover - admin chưa nạp
        return ""
    return f"{url}?di_tich={di_tich_id}" if di_tich_id else url


def check_image_file(f):
    """Kiểm tra tệp ảnh tải lên: phần mở rộng, dung lượng và định dạng thật (Pillow). Trả về thông báo lỗi hoặc ''."""
    from PIL import Image, UnidentifiedImageError

    from . import images as _images  # noqa: F401  (đăng ký bộ mở HEIC)

    name = os.path.basename(f.name or "")
    ext = os.path.splitext(name)[1].lower()
    if ext not in IMAGE_EXT:
        return f"“{name}”: chỉ nhận ảnh JPG, PNG, WebP, HEIC."
    if f.size > MAX_IMAGE:
        return f"“{name}” nặng {f.size / 1048576:.1f} MB, vượt mức tối đa 25 MB."
    try:
        pos = f.tell()
        img = Image.open(f)
        fmt = (img.format or "").upper()
        img.verify()
        f.seek(pos)
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        return f"“{name}” không phải tệp ảnh hợp lệ (hoặc tệp bị hỏng)."
    if fmt not in IMAGE_FORMATS:
        return f"“{name}”: định dạng {fmt or 'không rõ'} không được hỗ trợ."
    return ""


# Trợ giúp chi tiết, mở bằng nút (?) cạnh nhãn trường (TR FR-H01).
HELP_DETAIL = {
    "ma": "Mã dùng để quản lý và để nhập/cập nhật từ Excel. Viết liền, không dấu. Ví dụ: VD01, VD45. "
          "Không đổi mã sau khi đã xuất bản.",
    "ten_vi": "Ghi đúng tên trong quyết định xếp hạng hoặc danh mục kiểm kê. Ví dụ: Đình Quan Lạn. "
              "Tên khác (đền Cậu, chùa Lấm…) ghi ở ô “Tên gọi khác” để người dân tìm được.",
    "ten_khac": "Các tên dân gian, tên chữ Hán, tên cũ; cách nhau dấu phẩy. Ví dụ: Đền Cậu, Linh Quang tự.",
    "cap_xep_hang": "Quốc gia đặc biệt / Quốc gia / Cấp tỉnh: theo quyết định xếp hạng. "
                    "Kiểm kê: di tích có trong danh mục kiểm kê nhưng chưa xếp hạng.",
    "loai_hinh": "Có thể chọn nhiều loại. Ví dụ một ngôi đình vừa là di tích Lịch sử vừa là Kiến trúc nghệ thuật.",
    "khu_vuc": "Khu vực (đảo) nơi di tích tọa lạc. Dùng để lọc trên website và tính “cần đi tàu”.",
    "khu_vuc_phu": "Chỉ chọn khi di tích trải trên nhiều khu vực, ví dụ Quần thể Thương cảng Vân Đồn.",
    "dia_chi_moi_vi": "Theo đơn vị hành chính từ 01/7/2025. Ví dụ: Thôn Quan Lạn, đặc khu Vân Đồn, tỉnh Quảng Ninh.",
    "dia_chi_cu": "Địa chỉ trước 01/7/2025 (xã, huyện) để người dân dễ nhận ra. Ví dụ: Xã Quan Lạn, huyện Vân Đồn.",
    "so_quyet_dinh": "Ghi đủ số và ngày. Ví dụ: 313/VH-QĐ ngày 28/4/1962. Nhiều quyết định thì cách nhau dấu chấm phẩy.",
    "tom_tat_vi": "1–3 câu, tối đa 600 ký tự, nói di tích là gì, ở đâu, giá trị nổi bật. Hiện ở thẻ danh sách, "
                  "kết quả tìm kiếm và khi chia sẻ Facebook/Zalo. Ví dụ: “Đình Quan Lạn thờ ba anh em họ Phạm…”.",
    "noi_dung_vi": "Bấm “Tiêu đề mục” để tạo các mục: Lịch sử; Giá trị; Kiến trúc, cảnh quan; Truyền thuyết, tín ngưỡng; "
                   "Lễ hội. Dán từ Word được – hệ thống chỉ giữ đậm, nghiêng, danh sách, tiêu đề. "
                   "Chèn ảnh bằng nút “Ảnh từ thư viện” (ảnh phải tải lên ở thẻ Ảnh, video trước).",
    "thong_tin_tham_quan_vi": "Cách đi (tàu, xe), thời điểm nên đến, trang phục, lưu ý giữ gìn. "
                              "Ví dụ: Từ cảng Ao Tiên đi tàu cao tốc khoảng 45 phút ra cảng Quan Lạn…",
    "anh_dai_dien": "Ảnh hiện ở danh sách và đầu trang di tích. Cách nhanh nhất: bấm ngôi sao ★ trên ảnh trong lưới ảnh.",
    "trang_thai": "Nháp: đang soạn. Chờ duyệt: đã xong, chờ người duyệt. Đã xuất bản: hiện trên website. "
                  "Ẩn: tạm gỡ khỏi website. Chỉ người có quyền Duyệt nội dung mới chọn được Đã xuất bản / Ẩn.",
    "slug": "Phần cuối địa chỉ trang. Để trống, hệ thống tự tạo từ tên (không dấu). Đổi sau khi xuất bản sẽ làm hỏng "
            "các liên kết đã chia sẻ.",
    "seo_title_vi": "Dòng tiêu đề xanh hiện trên Google, tối đa khoảng 60 ký tự. Để trống: dùng tên di tích.",
    "seo_description_vi": "Hai dòng mô tả dưới tiêu đề trên Google, tối đa khoảng 160 ký tự. Để trống: dùng tóm tắt.",
    "tham_quan_duoc": "Bỏ chọn với phế tích, di chỉ khảo cổ không có gì để xem – website sẽ không gợi ý du khách tới.",
    "noi_bat": "Di tích nổi bật hiện ở trang chủ. Nên chọn 6–8 di tích tiêu biểu.",
}

HINTS = {
    "ma": "Ví dụ VD45. Không trùng với di tích khác.",
    "ten_vi": "Tên chính thức theo quyết định xếp hạng hoặc danh mục kiểm kê.",
    "dia_chi_moi_vi": "Ví dụ: Thôn Quan Lạn, đặc khu Vân Đồn, tỉnh Quảng Ninh.",
    "dia_chi_cu": "Địa chỉ cũ (xã, huyện) để người dân dễ nhận biết.",
    "so_quyet_dinh": "Ví dụ: 313/VH-QĐ ngày 28/4/1962.",
    "co_quan_qd": "Ví dụ: Bộ Văn hóa, Thể thao và Du lịch; UBND tỉnh Quảng Ninh.",
    "dien_tich": "Ghi kèm đơn vị, ví dụ 1.200 m².",
    "tom_tat_vi": "Bắt buộc. 1–3 câu (tối đa 600 ký tự).",
    "hien_trang_mo_ta_vi": "Ví dụ: Đã tu bổ năm 2015; mái ngói còn tốt.",
    "gio_mo_cua_vi": "Ví dụ: 7:00–17:00 hằng ngày; rằm, mùng một mở đến 21:00.",
    "phi_tham_quan_vi": "Ví dụ: Miễn phí.",
    "lien_he": "Ví dụ: Ban quản lý di tích, ĐT 0203 xxx xxx.",
    "thu_tu": "Số nhỏ hiển thị trước.",
    "slug": "Để trống để hệ thống tự tạo.",
    "seo_title_vi": "≤ 60 ký tự. Để trống: dùng tên di tích.",
    "seo_description_vi": "≤ 160 ký tự. Để trống: dùng tóm tắt.",
    "noi_dung_vi": "Chia mục bằng nút “Tiêu đề mục”.",
    "thong_tin_tham_quan_vi": "Cách đi, thời điểm nên đến, trang phục, lưu ý.",
    "ten_khac": "Tên dân gian, tên chữ… giúp tìm kiếm.",
}


class RichTextMixin:
    """Gắn trình soạn thảo trực quan cho các trường HTML (mọi ngôn ngữ)."""

    rich_fields = ()
    rich_ditich_attr = None  # "self" (DiTich) – lọc thư viện ảnh theo di tích

    def setup_rich(self):
        did = self.instance.pk if self.rich_ditich_attr == "self" else None
        url = picker_url(did)
        for base in self.rich_fields:
            for lang in LANGS:
                name = f"{base}_{lang}"
                if name in self.fields:
                    old = self.fields[name].widget.attrs
                    self.fields[name].widget = RichTextWidget(attrs={
                        "data-picker-url": url, "data-picker-all": picker_url(), "data-lang": lang,
                        **{k: v for k, v in old.items() if k.startswith("data-")}})


def add_help(fields, hints=None, details=None):
    for name, fld in fields.items():
        if hints and name in hints and not fld.help_text:
            fld.help_text = hints[name]
        if details and name in details:
            fld.widget.attrs["data-help"] = details[name]


class HinhAnhChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        label = obj.chu_thich_vi or obj.tep.name.rsplit("/", 1)[-1]
        extra = " (ảnh minh họa tạm)" if obj.la_minh_hoa else ""
        return f"Ảnh #{obj.pk} – {label[:70]}{extra}"


def publish_missing(data, instance):
    """Điều kiện xuất bản (FR-A09) tính trên dữ liệu đang nhập trong form."""
    miss = []
    if not (data.get("ten_vi") or "").strip():
        miss.append("tên tiếng Việt")
    if not (data.get("tom_tat_vi") or "").strip():
        miss.append("tóm tắt tiếng Việt")
    if not data.get("anh_dai_dien"):
        miss.append("ảnh đại diện")
    if not data.get("cap_xep_hang"):
        miss.append("cấp xếp hạng")
    if not data.get("khu_vuc"):
        miss.append("khu vực")
    return miss


class DiTichAdminForm(RichTextMixin, forms.ModelForm):
    rich_fields = ("noi_dung", "thong_tin_tham_quan")
    rich_ditich_attr = "self"
    request_user = None  # gán bởi DiTichAdmin.get_form

    class Meta:
        model = DiTich
        fields = "__all__"
        widgets = {
            "loai_hinh": forms.CheckboxSelectMultiple,
            "khu_vuc_phu": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_rich()
        data = self.data or {}
        # Lưu nháp (trình hướng dẫn, chuyển sang bước Ảnh): cho phép chưa có tóm tắt.
        self.is_draft_save = bool(data.get("_vd_draft"))
        if self.is_draft_save and "tom_tat_vi" in self.fields:
            self.fields["tom_tat_vi"].required = False
        for name in ("tom_tat_vi", "tom_tat_en", "tom_tat_zh_hans"):
            if name in self.fields:
                self.fields[name].widget.attrs.update({"rows": 3, "maxlength": 600, "data-counter": "600"})
        for name in ("seo_description_vi", "seo_description_en", "seo_description_zh_hans"):
            if name in self.fields:
                self.fields[name].widget.attrs.update({"data-counter": "160"})
        for name in ("seo_title_vi", "seo_title_en", "seo_title_zh_hans"):
            if name in self.fields:
                self.fields[name].widget.attrs.update({"data-counter": "60"})
        f = self.fields.get("anh_dai_dien")
        if f is not None:
            qs = HinhAnh.objects.filter(di_tich=self.instance) if self.instance.pk else HinhAnh.objects.none()
            nf = HinhAnhChoiceField(queryset=qs.order_by("thu_tu", "id"), required=False, label=f.label,
                                    empty_label="— Chưa chọn —",
                                    help_text="Bắt buộc khi xuất bản. Bấm ngôi sao ★ trên ảnh để chọn nhanh.")
            nf.widget.attrs.update({"class": "vdh-avatar-select"})
            self.fields["anh_dai_dien"] = nf
        tt = self.fields.get("trang_thai")
        if tt is not None:
            if not can_publish(self.request_user):
                current = self.instance.trang_thai if self.instance.pk else TrangThai.DRAFT
                allowed = {TrangThai.DRAFT, TrangThai.REVIEW, current}
                tt.choices = [c for c in TrangThai.choices if c[0] in allowed]
                tt.help_text = ("Bạn lưu được Nháp hoặc Chờ duyệt. Người có quyền Duyệt nội dung sẽ xuất bản.")
            else:
                tt.help_text = ("Chỉ xuất bản được khi có đủ: tên, tóm tắt tiếng Việt, ảnh đại diện, "
                                "cấp xếp hạng, khu vực.")
        add_help(self.fields, HINTS, HELP_DETAIL)
        if "ma" in self.fields:
            self.fields["ma"].help_text = HINTS["ma"]
        for lang in ("en", "zh_hans"):
            for name, fld in self.fields.items():
                if name.endswith("_" + lang) and not fld.help_text:
                    fld.help_text = (f"Bản {LANG_LABEL[lang]}. Để trống: trang công khai hiện bản tiếng Việt "
                                     "kèm nhãn “Bản dịch đang cập nhật”.")

    def clean_ma(self):
        ma = (self.cleaned_data.get("ma") or "").strip()
        if " " in ma:
            raise ValidationError("Mã viết liền, không có dấu cách. Ví dụ VD45.")
        return ma

    def clean(self):
        data = super().clean()
        value = data.get("trang_thai")
        initial = self.instance.trang_thai if self.instance.pk else None
        if value in PUBLISH_ONLY and value != initial and not can_publish(self.request_user):
            self.add_error("trang_thai", "Bạn chưa có quyền Xuất bản / Ẩn. Hãy chọn “Chờ duyệt” để gửi người duyệt.")
            return data
        if value == TrangThai.PUBLISHED:
            miss = publish_missing(data, self.instance)
            if miss:
                self.add_error("trang_thai", "Chưa thể xuất bản. Còn thiếu: " + ", ".join(miss) +
                               ". Hãy lưu ở trạng thái Nháp hoặc Chờ duyệt, bổ sung rồi xuất bản sau.")
        return data

    def _post_clean(self):
        # Điều kiện xuất bản đã kiểm tra ở clean(); tránh lặp lỗi từ DiTich.clean().
        super()._post_clean()
        errs = self._errors.get("trang_thai") if self._errors else None
        if errs and len(errs) > 1:
            self._errors["trang_thai"] = self.error_class(errs[:1])


class DiemDiTichInlineForm(forms.ModelForm):
    toa_do = forms.CharField(
        label="Tọa độ", required=False, max_length=120,
        help_text='Dán độ-phút-giây 20°53\'49.3"N 107°18\'33.7"E hoặc thập phân 20.897028, 107.309361 '
                  "rồi bấm “Đọc tọa độ”.",
        widget=forms.TextInput(attrs={"class": "vdh-coord-text", "autocomplete": "off", "spellcheck": "false",
                                      "placeholder": '20°53\'49.3"N 107°18\'33.7"E'}),
    )

    class Meta:
        model = DiemDiTich
        fields = "__all__"
        widgets = {
            "vi_do": forms.NumberInput(attrs={"step": "0.000001", "class": "vdh-lat", "placeholder": "20.897028"}),
            "kinh_do": forms.NumberInput(attrs={"step": "0.000001", "class": "vdh-lng", "placeholder": "107.309361"}),
            "thu_tu": forms.HiddenInput(attrs={"class": "vdh-order"}),
            "mo_ta_vi": forms.Textarea(attrs={"rows": 2}),
            "mo_ta_en": forms.Textarea(attrs={"rows": 2}),
            "mo_ta_zh_hans": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        inst = self.instance
        if inst.pk:
            self.fields["toa_do"].initial = inst.toa_do_goc or (
                f"{inst.vi_do}, {inst.kinh_do}" if inst.vi_do is not None else "")
        labels = {"ten_vi": ("Tên điểm (tiếng Việt)", "Ví dụ: Đình Quan Lạn"),
                  "ten_en": ("Tên tiếng Anh", "Quan Lan Communal House"),
                  "ten_zh_hans": ("Tên tiếng Trung", "官澜亭"),
                  "mo_ta_vi": ("Mô tả ngắn (tiếng Việt)", ""), "mo_ta_en": ("Mô tả ngắn (tiếng Anh)", ""),
                  "mo_ta_zh_hans": ("Mô tả ngắn (tiếng Trung)", "")}
        for name, (label, ph) in labels.items():
            if name in self.fields:
                self.fields[name].label = label
                if ph:
                    self.fields[name].widget.attrs["placeholder"] = ph
        if "vi_do" in self.fields:
            self.fields["vi_do"].help_text = "Số thập phân, ví dụ 20.897028."
        if "kinh_do" in self.fields:
            self.fields["kinh_do"].help_text = "Số thập phân, ví dụ 107.309361."
        if "do_tin_cay" in self.fields:
            self.fields["do_tin_cay"].help_text = "Mức độ chắc chắn của tọa độ."
        if "thu_tu" in self.fields:
            self.fields["thu_tu"].required = False
        self.fields["toa_do"].widget.attrs["data-help"] = (
            "Ba cách: (1) dán chuỗi độ-phút-giây như trong danh mục; (2) gõ số thập phân “vĩ độ, kinh độ”; "
            "(3) bấm trên bản đồ. Tại hiện trường: mở Google Maps, giữ ngón tay tại vị trí, sao chép dãy số rồi dán vào đây.")

    def clean_thu_tu(self):
        return self.cleaned_data.get("thu_tu") or 0

    def clean(self):
        data = super().clean()
        text = (data.get("toa_do") or "").strip()
        lat, lng = data.get("vi_do"), data.get("kinh_do")
        coord_changed = "toa_do" in self.changed_data
        num_changed = "vi_do" in self.changed_data or "kinh_do" in self.changed_data
        if text and (coord_changed or not num_changed or lat is None):
            try:
                plat, plng, note = parse_coordinates(text)
            except CoordinateError as e:
                self.add_error("toa_do", str(e))
                return data
            data["vi_do"], data["kinh_do"] = Decimal(f"{plat:.6f}"), Decimal(f"{plng:.6f}")
            self.instance.toa_do_goc = text[:120]
            self.coord_note = note
        elif lat is not None and lng is not None:
            self.instance.toa_do_goc = text[:120] if text else f"{lat}, {lng}"
        elif (lat is None) != (lng is None):
            self.add_error("toa_do", "Cần đủ cả vĩ độ và kinh độ.")
        else:
            self.instance.toa_do_goc = ""
        if data.get("vi_do") is not None and not (-90 <= data["vi_do"] <= 90):
            self.add_error("vi_do", "Vĩ độ phải trong khoảng −90 đến 90.")
        if data.get("kinh_do") is not None and not (-180 <= data["kinh_do"] <= 180):
            self.add_error("kinh_do", "Kinh độ phải trong khoảng −180 đến 180.")
        return data


class SortableInlineForm(forms.ModelForm):
    """Trường thu_tu ẩn – sắp bằng kéo thả."""

    class Meta:
        fields = "__all__"
        widgets = {"thu_tu": forms.HiddenInput(attrs={"class": "vdh-order"})}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        if "thu_tu" in self.fields:
            self.fields["thu_tu"].required = False

    def clean_thu_tu(self):
        return self.cleaned_data.get("thu_tu") or 0


class VideoInlineForm(forms.ModelForm):
    class Meta:
        model = Video
        fields = "__all__"
        widgets = {
            "youtube_url": forms.URLInput(attrs={"class": "vdh-yt-input", "placeholder": "https://www.youtube.com/watch?v=…"}),
            "tep": forms.ClearableFileInput(attrs={"accept": ".mp4,video/mp4"}),
            "thu_tu": forms.HiddenInput(attrs={"class": "vdh-order"}),
        }

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        hints = {"youtube_url": "Dán liên kết YouTube (ưu tiên kênh chính thức). Ảnh bìa tự hiện bên dưới.",
                 "tep": "Hoặc tải tệp MP4, tối đa 200 MB, nếu không có YouTube.",
                 "nguon": "Bắt buộc. Ví dụ: Trung tâm Truyền thông tỉnh Quảng Ninh.",
                 "tieu_de_vi": "Tiêu đề tiếng Việt (bắt buộc)."}
        for k_, v in hints.items():
            if k_ in self.fields:
                self.fields[k_].help_text = v
        if "thu_tu" in self.fields:
            self.fields["thu_tu"].required = False

    def clean_thu_tu(self):
        return self.cleaned_data.get("thu_tu") or 0

    def clean_tep(self):
        f = self.cleaned_data.get("tep")
        if f and hasattr(f, "size") and "tep" in self.changed_data:
            if not f.name.lower().endswith(".mp4"):
                raise ValidationError("Chỉ nhận tệp video .mp4.")
            if f.size > MAX_VIDEO:
                raise ValidationError(f"Tệp nặng {f.size / 1048576:.0f} MB, vượt mức tối đa 200 MB. "
                                      "Hãy đưa video lên YouTube rồi dán liên kết.")
        return f

    def clean_nguon(self):
        v = (self.cleaned_data.get("nguon") or "").strip()
        if not v:
            raise ValidationError("Bắt buộc ghi nguồn / bản quyền video.")
        return v


class HinhAnhAdminForm(forms.ModelForm):
    class Meta:
        model = HinhAnh
        fields = "__all__"

    def clean_tep(self):
        f = self.cleaned_data.get("tep")
        if f and "tep" in self.changed_data and hasattr(f, "size"):
            err = check_image_file(f)
            if err:
                raise ValidationError(err)
        return f


class RichAdminForm(RichTextMixin, forms.ModelForm):
    """Dùng cho Tuyến, Lễ hội, Thông tin hữu ích, Tin tức, Trang tĩnh."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.setup_rich()


def rich_form(model_cls, fields, base=RichAdminForm):
    return type(f"{model_cls.__name__}AdminForm", (base,),
                {"rich_fields": tuple(fields), "Meta": type("Meta", (), {"model": model_cls, "fields": "__all__"})})


class ImportUploadForm(forms.Form):
    file = forms.FileField(label="File Excel (.xlsx)",
                           help_text="Dùng đúng file mẫu. Dung lượng tối đa 10 MB.",
                           widget=forms.ClearableFileInput(attrs={"accept": ".xlsx"}))
    mode = forms.ChoiceField(label="Cách nhập", initial="new", widget=forms.RadioSelect,
                             choices=[("new", "Thêm mới – chỉ thêm các mã chưa có (mã đã có sẽ báo lỗi)"),
                                      ("update", "Cập nhật theo mã – mã đã có thì cập nhật, mã chưa có thì thêm mới")])

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith(".xlsx"):
            raise ValidationError("Chỉ nhận file .xlsx (Excel 2007 trở lên). Nếu là .xls, hãy mở và Lưu thành .xlsx.")
        if f.size > 10 * 1024 * 1024:
            raise ValidationError("File quá lớn (tối đa 10 MB).")
        return f
