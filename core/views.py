import base64
import io

from datetime import timedelta

import pyotp
import qrcode
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import logout
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .models import AdminProfile, HelpArticle
from .signals import log


def _profile(user):
    prof, _ = AdminProfile.objects.get_or_create(user=user)
    return prof


OTP_MAX_FAILS = 5


def _qr_b64(uri):
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@staff_member_required
def otp_setup(request):
    """Bật xác thực 2 lớp: quét QR bằng Google Authenticator / Microsoft Authenticator.

    Khi đã bật: chỉ hiển thị trạng thái và nút tắt / đặt lại (không lộ lại mã bí mật).
    """
    prof = _profile(request.user)
    if prof.otp_enabled and not request.session.get("otp_ok"):
        # Đã bật nhưng phiên này chưa nhập mã: không cho xem lại mã bí mật.
        return redirect(f"{reverse('core:otp_verify')}?next={request.path}")
    ctx = {**admin.site.each_context(request), "title": "Xác thực 2 lớp", "enabled": prof.otp_enabled,
           "required": request.user.is_superuser and settings.OTP_REQUIRED_FOR_SUPERUSER}
    if prof.otp_enabled:
        return render(request, "admin/otp_setup.html", ctx)
    if not prof.otp_secret or (request.method == "GET" and "new" in request.GET):
        prof.otp_secret = pyotp.random_base32()
        prof.save(update_fields=["otp_secret"])
    totp = pyotp.TOTP(prof.otp_secret)
    if request.method == "POST":
        code = request.POST.get("code", "").replace(" ", "")
        if totp.verify(code, valid_window=1):
            prof.otp_enabled = True
            prof.save(update_fields=["otp_enabled"])
            request.session["otp_ok"] = True
            log("other", request.user, user=request.user, repr_=f"Bật xác thực 2 lớp: {request.user.username}")
            messages.success(request, "Đã bật xác thực 2 lớp. Từ lần đăng nhập sau, hệ thống sẽ hỏi mã 6 số.")
            return redirect("admin:index")
        messages.error(request, "Mã không đúng. Kiểm tra giờ trên điện thoại (đặt tự động) và thử lại.")
    uri = totp.provisioning_uri(name=request.user.username, issuer_name="Di tich Van Don")
    secret = prof.otp_secret
    ctx.update(qr=_qr_b64(uri), secret=secret,
               secret_groups=" ".join(secret[i:i + 4] for i in range(0, len(secret), 4)))
    return render(request, "admin/otp_setup.html", ctx)


@staff_member_required
def otp_verify(request):
    prof = _profile(request.user)
    nxt = request.GET.get("next") or request.POST.get("next") or ""
    if not url_has_allowed_host_and_scheme(nxt, {request.get_host()}):
        nxt = ""
    if not prof.otp_enabled or not prof.otp_secret:
        return redirect("core:otp_setup")
    if request.session.get("otp_ok"):
        return redirect(nxt or "admin:index")
    if request.method == "POST":
        if pyotp.TOTP(prof.otp_secret).verify(request.POST.get("code", "").replace(" ", ""), valid_window=1):
            request.session["otp_ok"] = True
            request.session.pop("otp_fails", None)
            return redirect(nxt or "admin:index")
        fails = request.session.get("otp_fails", 0) + 1
        request.session["otp_fails"] = fails
        if fails >= OTP_MAX_FAILS:
            # Nhập sai mã quá nhiều lần: khóa tạm tài khoản như khi sai mật khẩu.
            prof.locked_until = timezone.now() + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
            prof.save(update_fields=["locked_until"])
            log("login_fail", user=None, repr_=f"Sai mã xác thực 2 lớp {fails} lần: {request.user.username}")
            logout(request)
            messages.error(request, f"Nhập sai mã {fails} lần. Tài khoản tạm khóa {settings.LOGIN_LOCK_MINUTES} phút.")
            return redirect("admin:login")
        messages.error(request, f"Mã xác thực không đúng (còn {OTP_MAX_FAILS - fails} lần thử).")
    ctx = {**admin.site.each_context(request), "title": "Nhập mã xác thực", "next": nxt}
    return render(request, "admin/otp_verify.html", ctx)


@staff_member_required
def help_index(request):
    ctx = {**admin.site.each_context(request), "title": "Hướng dẫn sử dụng", "articles": HelpArticle.objects.all()}
    return render(request, "admin/help/index.html", ctx)


@staff_member_required
def help_detail(request, slug):
    art = get_object_or_404(HelpArticle, slug=slug)
    ctx = {**admin.site.each_context(request), "title": art.title, "art": art,
           "articles": HelpArticle.objects.all()}
    return render(request, "admin/help/detail.html", ctx)
