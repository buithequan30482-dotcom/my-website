"""Tự quản lý xác thực 2 lớp: tắt / đặt lại (cần nhập mã hiện tại)."""
import pyotp
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from .models import AdminProfile
from .signals import log


def _check_code(request, prof):
    code = (request.POST.get("code") or "").replace(" ", "")
    if not (prof.otp_enabled and prof.otp_secret and pyotp.TOTP(prof.otp_secret).verify(code, valid_window=1)):
        messages.error(request, "Mã xác thực hiện tại không đúng. Thao tác chưa được thực hiện.")
        return False
    return True


@staff_member_required
@require_POST
def otp_disable(request):
    prof, _ = AdminProfile.objects.get_or_create(user=request.user)
    if request.user.is_superuser and settings.OTP_REQUIRED_FOR_SUPERUSER:
        messages.error(request, "Tài khoản Quản trị hệ thống bắt buộc dùng xác thực 2 lớp – chỉ có thể đặt lại.")
        return redirect("core:otp_setup")
    if _check_code(request, prof):
        prof.otp_enabled, prof.otp_secret = False, ""
        prof.save(update_fields=["otp_enabled", "otp_secret"])
        log("other", request.user, user=request.user, repr_=f"Tắt xác thực 2 lớp: {request.user.username}")
        messages.success(request, "Đã tắt xác thực 2 lớp. Nên bật lại để bảo vệ tài khoản.")
    return redirect("core:otp_setup")


@staff_member_required
@require_POST
def otp_reset(request):
    """Đổi điện thoại / cài lại ứng dụng: tạo mã bí mật mới và quét lại QR."""
    prof, _ = AdminProfile.objects.get_or_create(user=request.user)
    if _check_code(request, prof):
        prof.otp_enabled = False
        prof.otp_secret = pyotp.random_base32()
        prof.save(update_fields=["otp_enabled", "otp_secret"])
        request.session.pop("otp_ok", None)
        log("other", request.user, user=request.user, repr_=f"Đặt lại xác thực 2 lớp: {request.user.username}")
        messages.success(request, "Đã tạo mã mới. Quét mã QR dưới đây bằng ứng dụng trên điện thoại rồi nhập 6 số để hoàn tất.")
    return redirect("core:otp_setup")
