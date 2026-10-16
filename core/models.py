from django.conf import settings
from django.db import models
from django.utils import timezone


class SiteConfig(models.Model):
    """Cấu hình hệ thống – chỉ có một bản ghi (TR FR-A13)."""

    site_name = models.CharField("Tên website", max_length=200, default="Di tích Vân Đồn")
    tagline = models.CharField("Khẩu hiệu", max_length=300, blank=True, default="Nơi lưu dấu thương cảng cổ Đại Việt")
    google_maps_api_key = models.CharField(
        "Google Maps API key", max_length=200, blank=True,
        help_text="Khóa do cơ quan tạo trên Google Cloud. Để trống: hệ thống tự dùng bản đồ OpenStreetMap.",
    )
    owner_name = models.CharField("Cơ quan chủ quản", max_length=200, default="Phòng Văn hóa – Xã hội, Đặc khu Vân Đồn")
    address = models.CharField("Địa chỉ", max_length=300, blank=True)
    phone = models.CharField("Điện thoại", max_length=50, blank=True)
    email = models.EmailField("Email liên hệ", blank=True)
    facebook_url = models.URLField("Facebook", blank=True)
    youtube_url = models.URLField("YouTube", blank=True)
    zalo_url = models.URLField("Zalo OA", blank=True)
    notify_emails = models.CharField(
        "Email nhận thông báo", max_length=500, blank=True,
        help_text="Nhiều email cách nhau bằng dấu phẩy. Nhận thông báo khi có báo di tích xuống cấp hoặc nhiều nhận xét chờ duyệt.",
    )
    pending_threshold = models.PositiveIntegerField("Ngưỡng cảnh báo chờ duyệt", default=20)
    hero_video_url = models.URLField("Video nền trang chủ (YouTube)", blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cấu hình hệ thống"
        verbose_name_plural = "Cấu hình hệ thống"

    def __str__(self):
        return "Cấu hình hệ thống"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def maps_key(self):
        return self.google_maps_api_key or settings.GOOGLE_MAPS_API_KEY


class AdminProfile(models.Model):
    """Thông tin bảo mật bổ sung cho tài khoản quản trị (2FA, khóa tạm)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="admin_profile")
    otp_secret = models.CharField(max_length=64, blank=True)
    otp_enabled = models.BooleanField("Đã bật xác thực 2 lớp", default=False)
    failed_logins = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Bảo mật tài khoản"
        verbose_name_plural = "Bảo mật tài khoản"

    def is_locked(self):
        return self.locked_until and self.locked_until > timezone.now()


class AuditLog(models.Model):
    """Nhật ký thao tác (TR FR-A12)."""

    ACTIONS = [
        ("create", "Tạo"), ("update", "Sửa"), ("delete", "Xóa"), ("publish", "Xuất bản"),
        ("approve", "Duyệt"), ("hide", "Ẩn"), ("login", "Đăng nhập"), ("login_fail", "Đăng nhập sai"),
        ("export", "Xuất báo cáo"), ("import", "Nhập dữ liệu"), ("other", "Khác"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Người dùng")
    username = models.CharField("Tài khoản", max_length=150, blank=True)
    action = models.CharField("Hành động", max_length=20, choices=ACTIONS)
    object_type = models.CharField("Đối tượng", max_length=100, blank=True)
    object_id = models.CharField("Mã", max_length=64, blank=True)
    object_repr = models.CharField("Mô tả", max_length=300, blank=True)
    changes = models.JSONField("Thay đổi", null=True, blank=True)
    ip = models.CharField("IP", max_length=64, blank=True)
    created_at = models.DateTimeField("Thời gian", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "Nhật ký thao tác"
        verbose_name_plural = "Nhật ký thao tác"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%d/%m/%Y %H:%M} {self.username} {self.get_action_display()} {self.object_repr}"


class HelpArticle(models.Model):
    """Bài hướng dẫn sử dụng trong khu quản trị (TR FR-H03)."""

    slug = models.SlugField(unique=True)
    title = models.CharField("Tiêu đề", max_length=200)
    order = models.PositiveIntegerField("Thứ tự", default=0)
    summary = models.CharField("Tóm tắt", max_length=300, blank=True)
    body = models.TextField("Nội dung (HTML)")
    video_url = models.URLField("Video hướng dẫn", blank=True)

    class Meta:
        verbose_name = "Bài hướng dẫn"
        verbose_name_plural = "Hướng dẫn sử dụng"
        ordering = ["order"]

    def __str__(self):
        return self.title
