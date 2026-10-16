import threading

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

_local = threading.local()


def current_user():
    return getattr(_local, "user", None)


def current_ip():
    return getattr(_local, "ip", "")


class AuditUserMiddleware:
    """Ghi nhớ người dùng hiện tại để nhật ký thao tác biết ai làm."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from .utils import client_ip
        _local.user = getattr(request, "user", None)
        _local.ip = client_ip(request)
        try:
            return self.get_response(request)
        finally:
            _local.user = None
            _local.ip = ""


class SecurityHeadersMiddleware:
    """Header bảo mật bổ sung (TR 8.2). CSP cho phép Google Maps, OSM, YouTube."""

    CSP = (
        "default-src 'self'; "
        "img-src 'self' data: blob: https://*.googleapis.com https://*.gstatic.com https://*.google.com "
        "https://*.tile.openstreetmap.org https://server.arcgisonline.com https://i.ytimg.com "
        "https:; "  # ảnh từ liên kết ngoài (HinhAnh.url_ngoai) – chỉ ảnh, không áp dụng cho script/iframe

        "script-src 'self' 'unsafe-inline' https://maps.googleapis.com https://maps.gstatic.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "frame-src https://www.google.com https://maps.google.com https://www.youtube-nocookie.com https://www.youtube.com; "
        "connect-src 'self' https://maps.googleapis.com https://nominatim.openstreetmap.org; "
        "frame-ancestors 'self'; base-uri 'self'; form-action 'self'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resp = self.get_response(request)
        resp.setdefault("Content-Security-Policy", self.CSP)
        resp.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(self)")
        return resp


class AdminOTPMiddleware:
    """Bắt buộc nhập mã OTP (2 lớp) cho tài khoản đã bật, và cho quản trị hệ thống (TR FR-A01)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        admin_prefix = "/" + settings.ADMIN_URL
        path = request.path
        user = getattr(request, "user", None)
        if (path.startswith(admin_prefix) and user is not None and user.is_authenticated and user.is_staff
                and not request.session.get("otp_ok")):
            allowed = [reverse("core:otp_verify"), reverse("core:otp_setup"), reverse("admin:logout")]
            if not any(path.startswith(a) for a in allowed) and not path.startswith(admin_prefix + "jsi18n"):
                prof = getattr(user, "admin_profile", None)
                if prof and prof.otp_enabled:
                    return redirect(f"{reverse('core:otp_verify')}?next={path}")
                if user.is_superuser and settings.OTP_REQUIRED_FOR_SUPERUSER:
                    return redirect(reverse("core:otp_setup"))
        return self.get_response(request)
