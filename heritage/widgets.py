"""Widget dùng trong khu quản trị nội dung."""
from django import forms

CSS = "vd-admin/heritage/heritage-admin.css"


class RichTextWidget(forms.Textarea):
    """Trình soạn thảo trực quan (Quill 2.0.3, tự host ở static/vendor/quill) – TR FR-A07.

    Textarea gốc vẫn được gửi lên máy chủ (HTML đồng bộ mỗi lần gõ); máy chủ làm sạch bằng
    core.utils.clean_html khi lưu model. Thanh công cụ: Tiêu đề mục (h3), Tiêu đề nhỏ (h4), đậm, nghiêng,
    danh sách, danh sách số, trích dẫn, liên kết, chèn ảnh từ thư viện, xóa định dạng.
    Thuộc tính:
        data-picker-url  – endpoint JSON liệt kê ảnh (lọc theo di tích nếu có)
        data-picker-all  – endpoint liệt kê ảnh mới nhất toàn hệ thống
    """

    def __init__(self, attrs=None):
        base = {"class": "vdh-richtext", "rows": 12}
        if attrs:
            base.update(attrs)
        super().__init__(attrs=base)

    class Media:
        css = {"all": ("vendor/quill/quill.snow.css", CSS)}
        js = ("vd-admin/heritage/common.js", "vendor/quill/quill.js", "vd-admin/heritage/richtext.js")
