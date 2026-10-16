"""Chuỗi hiển thị công khai không bọc gettext trong models (nhãn loại góp ý, trạng thái xử lý).

Chỉ để makemessages trích xuất; template dùng {% trans obj.get_loai_display %}.
"""
from django.utils.translation import gettext_noop

STRINGS = [
    # GopY.Loai
    gettext_noop("Góp ý dịch vụ"),
    gettext_noop("Mong muốn, đề xuất"),
    gettext_noop("Báo di tích xuống cấp"),
    gettext_noop("Hỏi đáp"),
    gettext_noop("Khác"),
    # GopY.XuLy
    gettext_noop("Mới"),
    gettext_noop("Đang xử lý"),
    gettext_noop("Đã xử lý"),
    gettext_noop("Đóng"),
]
