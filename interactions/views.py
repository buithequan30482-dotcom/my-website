"""Tương tác người dùng: đánh giá, góp ý, tra cứu, "Muốn đến" (TR 5.2)."""
import logging
import uuid

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.models import SiteConfig
from core.utils import client_ip, hash_ip
from heritage.models import DiTich

from .forms import DanhGiaForm, GopYForm
from .models import AnhGopY, DanhGia, GopY, TrangThaiDuyet, YeuThich
from .tracking import track

log = logging.getLogger(__name__)
MAX_IMG = 5 * 1024 * 1024


def _rate_limited(request, kind):
    """Giới hạn số lượt gửi/giờ/IP (đếm theo IP đã băm)."""
    key = f"rl:{kind}:{hash_ip(client_ip(request))}"
    n = cache.get(key, 0)
    if n >= settings.SUBMIT_RATE_LIMIT_PER_HOUR:
        return True
    cache.set(key, n + 1, 3600)
    return False


def _notify(subject, body):
    cfg = SiteConfig.get()
    to = [e.strip() for e in (cfg.notify_emails or "").split(",") if e.strip()]
    if not to:
        return
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, to, fail_silently=True)
    except Exception:  # pragma: no cover
        log.exception("Gửi email thông báo thất bại")


def _check_pending_threshold():
    cfg = SiteConfig.get()
    n = DanhGia.objects.filter(trang_thai=TrangThaiDuyet.PENDING).count()
    if n == cfg.pending_threshold:
        _notify("[Di tích Vân Đồn] Nhiều nhận xét chờ duyệt", f"Hiện có {n} nhận xét chờ duyệt.")


@require_POST
def review_submit(request, slug):
    d = get_object_or_404(DiTich.objects.published(), slug=slug)
    form = DanhGiaForm(request.POST)
    if form.is_valid():
        if form.is_bot():
            messages.success(request, _("Cảm ơn bạn! Nhận xét sẽ hiển thị sau khi được kiểm duyệt."))
            return redirect(d.get_absolute_url() + "#danh-gia")
        if _rate_limited(request, "review"):
            messages.error(request, _("Bạn đã gửi quá nhiều lần trong một giờ. Vui lòng thử lại sau."))
            return redirect(d.get_absolute_url() + "#danh-gia")
        obj = form.save(commit=False)
        obj.di_tich = d
        obj.ngon_ngu = translation.get_language() or "vi"
        obj.ip_hash = hash_ip(client_ip(request))
        reasons = form.suspicious(obj.noi_dung + " " + obj.ten_hien_thi)
        if reasons:
            obj.nghi_spam, obj.ly_do_nghi = True, "; ".join(reasons)[:200]
        obj.save()
        _check_pending_threshold()
        messages.success(request, _("Cảm ơn bạn! Nhận xét sẽ hiển thị sau khi được kiểm duyệt."))
        return redirect(d.get_absolute_url() + "#danh-gia")
    # lỗi: hiển thị lại trang chi tiết với form lỗi
    from heritage.views import site_detail
    request.review_form = form
    return site_detail(request, slug)


def feedback(request):
    if request.method == "POST":
        form = GopYForm(request.POST)
        files = request.FILES.getlist("anh")[:3]
        bad_file = next((f for f in files if f.size > MAX_IMG or not (f.content_type or "").startswith("image/")), None)
        if bad_file:
            form.is_valid()
            form.add_error(None, _("Ảnh đính kèm phải là tệp ảnh, tối đa 5 MB mỗi ảnh."))
        elif form.is_valid():
            if form.is_bot():
                return redirect("interactions:feedback_done", ma="GY-0000-00000")
            if _rate_limited(request, "feedback"):
                form.add_error(None, _("Bạn đã gửi quá nhiều lần trong một giờ. Vui lòng thử lại sau."))
            else:
                obj = form.save(commit=False)
                obj.ngon_ngu = translation.get_language() or "vi"
                obj.ip_hash = hash_ip(client_ip(request))
                obj.nghi_spam = bool(form.suspicious(obj.noi_dung))
                obj.save()
                from PIL import Image
                for f in files:
                    try:
                        Image.open(f).verify()
                        f.seek(0)
                        AnhGopY.objects.create(gop_y=obj, tep=f)
                    except Exception:
                        pass
                if obj.loai == GopY.Loai.XUONG_CAP:
                    _notify(f"[Di tích Vân Đồn] Báo di tích xuống cấp {obj.ma_tra_cuu}",
                            f"Di tích: {obj.di_tich or 'không chọn'}\nNội dung:\n{obj.noi_dung}")
                return redirect("interactions:feedback_done", ma=obj.ma_tra_cuu)
    else:
        form = GopYForm(initial={"di_tich": request.GET.get("di_tich") or None, "loai": request.GET.get("loai") or None})
        form.init_ts()
        track(request)
    if not form.fields["ts"].initial:
        form.init_ts()
    public_qa = GopY.objects.filter(cong_khai=True).exclude(phan_hoi="").order_by("-ngay_tao")[:10]
    return render(request, "public/feedback.html", {"form": form, "public_qa": public_qa})


def feedback_done(request, ma):
    return render(request, "public/feedback_done.html", {"ma": ma})


def lookup(request):
    ma = (request.GET.get("ma") or "").strip().upper()
    obj = GopY.objects.filter(ma_tra_cuu=ma).first() if ma else None
    return render(request, "public/lookup.html", {"ma": ma, "obj": obj, "searched": bool(ma)})


@require_POST
def want_to_go(request, slug):
    """Nút "Muốn đến": 1 lượt/trình duyệt/di tích, dùng mã ngẫu nhiên ẩn danh lưu trong cookie chức năng."""
    d = get_object_or_404(DiTich.objects.published(), slug=slug)
    bid = request.COOKIES.get("vd_bid") or uuid.uuid4().hex
    _, created = YeuThich.objects.get_or_create(di_tich=d, ma_trinh_duyet=bid)
    resp = JsonResponse({"count": YeuThich.objects.filter(di_tich=d).count(), "created": created})
    resp.set_cookie("vd_bid", bid, max_age=3600 * 24 * 365 * 2, samesite="Lax", httponly=True)
    return resp
