import re
import time

from django import forms
from django.core import signing
from django.utils.translation import gettext_lazy as _

from heritage.models import DiTich

from .models import DanhGia, GopY, TuCam

URL_RE = re.compile(r"(https?://|www\.|\.com\b|\.vn\b|\.net\b)", re.I)


class AntiSpamMixin(forms.Form):
    """Trường bẫy ẩn + kiểm tra thời gian điền form (TR FR-I06)."""
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))
    ts = forms.CharField(required=False, widget=forms.HiddenInput)

    def init_ts(self):
        self.fields["ts"].initial = signing.dumps(int(time.time()))

    def is_bot(self, min_seconds=3):
        if self.cleaned_data.get("website"):
            return True
        try:
            t0 = signing.loads(self.cleaned_data.get("ts") or "", max_age=86400)
        except signing.BadSignature:
            return True
        return time.time() - t0 < min_seconds

    @staticmethod
    def suspicious(text):
        reasons = []
        if URL_RE.search(text or ""):
            reasons.append("chứa liên kết")
        low = (text or "").lower()
        bad = [w.tu for w in TuCam.objects.all() if w.tu.lower() in low]
        if bad:
            reasons.append("từ ngữ cấm: " + ", ".join(bad[:3]))
        if len(set(low)) < 6 and len(low) > 20:
            reasons.append("nội dung lặp")
        return reasons


def _contact_consent(form, cd):
    if (cd.get("email") or cd.get("dien_thoai")) and not cd.get("dong_y"):
        form.add_error("dong_y", _("Vui lòng đồng ý chính sách dữ liệu khi để lại email hoặc số điện thoại."))
    phone = cd.get("dien_thoai") or ""
    if phone and not re.fullmatch(r"[0-9+ ().-]{8,20}", phone):
        form.add_error("dien_thoai", _("Số điện thoại không hợp lệ."))


class DanhGiaForm(AntiSpamMixin, forms.ModelForm):
    so_sao = forms.TypedChoiceField(choices=[(i, i) for i in range(1, 6)], coerce=int, widget=forms.RadioSelect,
                                    label=_("Đánh giá của bạn"),
                                    error_messages={"required": _("Vui lòng chọn số sao.")})
    noi_dung = forms.CharField(min_length=20, max_length=1000, label=_("Nhận xét"),
                               widget=forms.Textarea(attrs={"rows": 4}),
                               error_messages={"min_length": _("Nhận xét cần ít nhất 20 ký tự.")})
    ten_hien_thi = forms.CharField(max_length=80, label=_("Tên hiển thị"))
    email = forms.EmailField(required=False, label=_("Email (không bắt buộc)"))
    dien_thoai = forms.CharField(required=False, max_length=20, label=_("Điện thoại (không bắt buộc)"))
    dong_y = forms.BooleanField(required=False, label=_("Tôi đồng ý với chính sách xử lý dữ liệu cá nhân"))

    class Meta:
        model = DanhGia
        fields = ["so_sao", "noi_dung", "ten_hien_thi", "email", "dien_thoai", "dong_y"]

    def clean(self):
        cd = super().clean()
        _contact_consent(self, cd)
        return cd


class GopYForm(AntiSpamMixin, forms.ModelForm):
    loai = forms.ChoiceField(choices=GopY.Loai.choices, label=_("Loại góp ý"))
    di_tich = forms.ModelChoiceField(queryset=DiTich.objects.published().order_by("ten"), required=False,
                                     label=_("Di tích liên quan (không bắt buộc)"), empty_label=_("— Không chọn —"))
    noi_dung = forms.CharField(min_length=10, max_length=3000, label=_("Nội dung"),
                               widget=forms.Textarea(attrs={"rows": 6}))
    ho_ten = forms.CharField(required=False, max_length=100, label=_("Họ tên (không bắt buộc)"))
    email = forms.EmailField(required=False, label=_("Email (không bắt buộc)"))
    dien_thoai = forms.CharField(required=False, max_length=20, label=_("Điện thoại (không bắt buộc)"))
    dong_y = forms.BooleanField(required=False, label=_("Tôi đồng ý với chính sách xử lý dữ liệu cá nhân"))

    class Meta:
        model = GopY
        fields = ["loai", "di_tich", "noi_dung", "ho_ten", "email", "dien_thoai", "dong_y"]

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["loai"].choices = [(k, _(v)) for k, v in GopY.Loai.choices]

    def clean(self):
        cd = super().clean()
        _contact_consent(self, cd)
        return cd
