"""View bổ sung cho khu quản trị di tích: ảnh (tải lên, đại diện, sắp xếp, sửa, xóa), thư viện ảnh (JSON),
xem trước, trình hướng dẫn, nhập / xuất Excel.

Các view được bọc bằng admin_site.admin_view trong DiTichAdmin.get_urls() / HinhAnhAdmin.get_urls()
(chỉ tài khoản staff đã đăng nhập mới truy cập được).
"""
import json
import os
import re
import secrets

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Avg, Count, Max, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone, translation
from django.views.decorators.http import require_POST

from core.middleware import SecurityHeadersMiddleware

from . import importer
from .admin_forms import ImportUploadForm, can_publish, check_image_file
from .images import MIN_RECOMMENDED
from .models import DiTich, HinhAnh

SESSION_PREFIX = "vd_import_"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Nguồn bổ sung cho bản đồ chọn tọa độ trong khu quản trị: ảnh vệ tinh Esri, tìm địa danh Nominatim, Google Places.
# Người tích hợp nên đưa các nguồn này vào core.middleware.SecurityHeadersMiddleware.CSP; trong lúc chờ, trang sửa
# di tích tự đặt CSP mở rộng (middleware dùng setdefault nên giữ nguyên giá trị này).
EXTRA_CSP = {
    "img-src": ["https://server.arcgisonline.com", "https://*.arcgisonline.com", "https://i.ytimg.com"],
    "connect-src": ["https://nominatim.openstreetmap.org", "https://*.googleapis.com"],
}


def with_extra_csp(response, extra=EXTRA_CSP):
    csp = SecurityHeadersMiddleware.CSP
    for directive, sources in extra.items():
        def add(m):
            have = m.group(1).split()
            return " ".join(have + [s for s in sources if s not in have])
        csp = re.sub(rf"({directive} [^;]*)", add, csp, count=1)
    response["Content-Security-Policy"] = csp
    return response


def _json_error(msg, status=400):
    return JsonResponse({"ok": False, "error": msg}, status=status)


def image_json(h, avatar_id=None):
    return {
        "id": h.pk, "thumb": h.url(480), "large": h.url(1600), "width": h.rong, "height": h.cao,
        "chu_thich_vi": h.chu_thich_vi or "", "chu_thich_en": h.chu_thich_en or "",
        "chu_thich_zh_hans": h.chu_thich_zh_hans or "", "tac_gia": h.tac_gia, "nguon": h.nguon,
        "la_minh_hoa": h.la_minh_hoa, "small": bool(h.rong and h.rong < MIN_RECOMMENDED),
        "avatar": avatar_id == h.pk, "name": os.path.basename(h.tep.name or ""),
    }


def gallery_data(obj):
    if not obj or not obj.pk:
        return []
    return [image_json(h, obj.anh_dai_dien_id) for h in obj.hinh_anh.order_by("thu_tu", "id")]


def _can_edit_images(request):
    u = request.user
    return u.has_perm("heritage.change_ditich") and u.has_perm("heritage.change_hinhanh")


# ------------------------------------------------------------------ Tải ảnh (FR-A05)
@require_POST
def upload_image(request, model_admin, object_id):
    """Nhận một ảnh / một lần gọi (XHR từ vùng kéo-thả). Trả JSON."""
    if not (request.user.has_perm("heritage.add_hinhanh") and request.user.has_perm("heritage.change_ditich")):
        return _json_error("Bạn chưa có quyền tải ảnh.", 403)
    ditich = get_object_or_404(DiTich, pk=object_id)
    f = request.FILES.get("file")
    nguon = (request.POST.get("nguon") or "").strip()
    tac_gia = (request.POST.get("tac_gia") or "").strip()
    if not nguon:
        return _json_error("Chưa nhập “Nguồn / bản quyền” cho đợt tải.")
    if not f:
        return _json_error("Không nhận được tệp.")
    err = check_image_file(f)
    if err:
        return _json_error(err)
    f.seek(0)
    name = os.path.basename(f.name)
    order = (HinhAnh.objects.filter(di_tich=ditich).aggregate(m=Max("thu_tu"))["m"] or 0) + 1
    h = HinhAnh(di_tich=ditich, tep=f, nguon=nguon[:300], tac_gia=tac_gia[:200], thu_tu=order)
    try:
        h.save()  # signal sinh biến thể WebP, gán h._warnings
    except Exception:
        if h.pk:
            h.delete()
        return _json_error(f"Không xử lý được “{name}”. Hãy thử lưu lại ảnh dưới dạng JPG rồi tải lên.", 400)
    warnings = list(getattr(h, "_warnings", []) or [])
    h.refresh_from_db()
    made_avatar = False
    if ditich.anh_dai_dien_id is None:  # chưa có ảnh đại diện: lấy ảnh thật đầu tiên
        DiTich.objects.filter(pk=ditich.pk, anh_dai_dien__isnull=True).update(anh_dai_dien=h)
        made_avatar = True
    data = image_json(h, h.pk if made_avatar else None)
    data.update({"ok": True, "warnings": warnings, "url": data["thumb"], "name": name})
    return JsonResponse(data)


def _image_of(object_id, image_id):
    return get_object_or_404(HinhAnh, pk=image_id, di_tich_id=object_id)


@require_POST
def image_set_avatar(request, model_admin, object_id, image_id):
    if not request.user.has_perm("heritage.change_ditich"):
        return _json_error("Bạn chưa có quyền sửa di tích.", 403)
    h = _image_of(object_id, image_id)
    d = h.di_tich
    d.anh_dai_dien = h
    d.nguoi_sua = request.user
    d.save(update_fields=["anh_dai_dien", "nguoi_sua", "ngay_sua"])
    msg = "Đã đặt làm ảnh đại diện."
    if h.la_minh_hoa:
        msg += " Lưu ý: đây là ảnh minh họa tạm."
    return JsonResponse({"ok": True, "id": h.pk, "message": msg})


@require_POST
def image_update(request, model_admin, object_id, image_id):
    """Lưu chú thích, tác giả, nguồn của một ảnh (gọi khi rời ô nhập)."""
    if not _can_edit_images(request):
        return _json_error("Bạn chưa có quyền sửa ảnh.", 403)
    h = _image_of(object_id, image_id)
    fields = {"chu_thich_vi": 300, "chu_thich_en": 300, "chu_thich_zh_hans": 300, "tac_gia": 200, "nguon": 300}
    changed = []
    for name, mx in fields.items():
        if name in request.POST:
            v = request.POST[name].strip()[:mx]
            if name == "nguon" and not v:
                return _json_error("Nguồn / bản quyền là bắt buộc – không để trống.")
            setattr(h, name, v)
            changed.append(name)
    if changed:
        h.save(update_fields=changed)
    return JsonResponse({"ok": True, "id": h.pk})


@require_POST
def image_delete(request, model_admin, object_id, image_id):
    if not request.user.has_perm("heritage.delete_hinhanh"):
        return _json_error("Bạn chưa có quyền xóa ảnh. Hãy nhờ người có quyền Duyệt nội dung.", 403)
    h = _image_of(object_id, image_id)
    was_avatar = DiTich.objects.filter(pk=object_id, anh_dai_dien=h).exists()
    h.delete()
    return JsonResponse({"ok": True, "id": int(image_id), "was_avatar": was_avatar})


@require_POST
def image_order(request, model_admin, object_id):
    if not _can_edit_images(request):
        return _json_error("Bạn chưa có quyền sắp xếp ảnh.", 403)
    get_object_or_404(DiTich, pk=object_id)
    ids = [int(x) for x in re.findall(r"\d+", request.POST.get("ids", ""))]
    with transaction.atomic():
        own = set(HinhAnh.objects.filter(di_tich_id=object_id, pk__in=ids).values_list("pk", flat=True))
        for i, pk in enumerate(p for p in ids if p in own):
            HinhAnh.objects.filter(pk=pk).update(thu_tu=i + 1)
    return JsonResponse({"ok": True, "count": len(own)})


def image_list(request, model_admin, object_id):
    if not model_admin.has_view_permission(request):
        raise PermissionDenied
    d = get_object_or_404(DiTich, pk=object_id)
    return JsonResponse({"items": gallery_data(d)})


# ------------------------------------------------------------------ Thư viện ảnh (trình soạn thảo)
def image_picker(request, model_admin):
    if not request.user.has_perm("heritage.view_hinhanh"):
        raise PermissionDenied
    qs = HinhAnh.objects.select_related("di_tich").order_by("-id")
    did = request.GET.get("di_tich")
    q = (request.GET.get("q") or "").strip()
    if did and did.isdigit():
        qs = qs.filter(di_tich_id=int(did)).order_by("thu_tu", "id")
    if q:
        qs = qs.filter(Q(chu_thich_vi__icontains=q) | Q(di_tich__ten_vi__icontains=q) | Q(di_tich__ma__iexact=q)
                       | Q(nguon__icontains=q))
    items = [{
        "id": h.pk, "url": h.url(960), "thumb": h.url(480), "caption": h.chu_thich_vi or "",
        "source": h.nguon, "placeholder": h.la_minh_hoa, "ditich": h.di_tich.ma if h.di_tich_id else "",
    } for h in qs[:80]]
    return JsonResponse({"items": items, "scoped": bool(did)})


# ------------------------------------------------------------------ Xem trước (FR-A03)
PREVIEW_BANNER = (
    '<div role="status" style="position:sticky;top:0;z-index:9999;background:#A3302A;color:#fff;'
    'font:600 15px/1.4 system-ui,sans-serif;padding:10px 16px;text-align:center">'
    'XEM TRƯỚC – trạng thái: {status}. Trang này chỉ người quản trị xem được. '
    '<a href="{back}" style="color:#fff;text-decoration:underline">Quay lại sửa</a></div>'
)


def preview(request, model_admin, object_id):
    """Hiển thị trang công khai của di tích (kể cả khi chưa xuất bản) – chỉ staff có quyền xem."""
    if not model_admin.has_view_permission(request):
        raise PermissionDenied
    from django.utils.html import escape

    from heritage.views import js, map_points

    lang = request.GET.get("lang", "vi")
    if lang not in ("vi", "en", "zh-hans"):
        lang = "vi"
    with translation.override(lang):
        d = get_object_or_404(DiTich.objects.select_related("khu_vuc", "anh_dai_dien").prefetch_related(
            "loai_hinh", "diem", "hinh_anh", "videos", "nguon", "le_hoi"), pk=object_id)
        if not d.slug:
            raise Http404
        from interactions.models import TrangThaiDuyet
        reviews = d.danh_gia.filter(trang_thai=TrangThaiDuyet.APPROVED).order_by("-ngay_tao")
        agg = reviews.aggregate(avg=Avg("so_sao"), n=Count("id"))
        dist = {i: 0 for i in range(5, 0, -1)}
        for r in reviews.values("so_sao").annotate(c=Count("id")):
            dist[r["so_sao"]] = r["c"]
        points = list(d.diem.all())
        i = 0
        for p in points:
            if p.has_coord:
                p.map_index = i
                i += 1
        lang_field = {"vi": "vi", "en": "en", "zh-hans": "zh_hans"}[lang]
        ctx = {
            "d": d, "points": points, "main": d.diem_chinh, "review_form": None,
            "points_json": js(map_points([d])), "gallery": list(d.hinh_anh.all()), "videos": list(d.videos.all()),
            "reviews": reviews[:20], "agg": agg, "dist": dist, "near": [],
            "untranslated": lang != "vi" and not getattr(d, f"tom_tat_{lang_field}", ""), "muon_den": 0,
            "embed_single": len([p for p in points if p.has_coord]) == 1,
            "abs_url": request.build_absolute_uri(d.get_absolute_url()), "is_preview": True,
        }
        resp = render(request, "public/detail.html", ctx)
    html = resp.content.decode("utf-8")
    banner = PREVIEW_BANNER.format(status=escape(d.get_trang_thai_display()),
                                   back=reverse("admin:heritage_ditich_change", args=[d.pk]))
    html = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + banner, html, count=1)
    out = HttpResponse(html, content_type="text/html; charset=utf-8")
    out["X-Robots-Tag"] = "noindex, nofollow"
    out["Cache-Control"] = "no-store"
    return out


# ------------------------------------------------------------------ Trình hướng dẫn (FR-H02)
def wizard(request, model_admin):
    if not model_admin.has_add_permission(request):
        raise PermissionDenied
    return redirect(reverse("admin:heritage_ditich_add") + "?wizard=1")


# ------------------------------------------------------------------ Nhập / xuất Excel (FR-A08)
def import_template(request, model_admin):
    if not model_admin.has_view_permission(request):
        raise PermissionDenied
    resp = HttpResponse(importer.build_template(), content_type=XLSX)
    resp["Content-Disposition"] = 'attachment; filename="mau-nhap-di-tich.xlsx"'
    return resp


def export_excel(request, queryset):
    from core.signals import log
    data = importer.export_workbook(queryset)
    log("export", repr_=f"Xuất Excel danh sách {queryset.count()} di tích")
    resp = HttpResponse(data, content_type=XLSX)
    resp["Content-Disposition"] = f'attachment; filename="di-tich-{timezone.localdate():%Y%m%d}.xlsx"'
    return resp


def _ctx(request, model_admin, **extra):
    ctx = dict(model_admin.admin_site.each_context(request), opts=model_admin.model._meta,
               title="Nhập di tích từ Excel", has_view_permission=True,
               template_url=reverse("admin:heritage_ditich_import_template"),
               import_url=reverse("admin:heritage_ditich_import"),
               changelist_url=reverse("admin:heritage_ditich_changelist"),
               can_update=model_admin.has_change_permission(request))
    ctx.update(extra)
    return ctx


def _preview_ctx(request, model_admin, data, token, mode):
    rows = data["rows"]
    for r in rows:
        r["errors_new"] = importer.row_errors(r, "new")
        r["errors_update"] = importer.row_errors(r, "update")
    return _ctx(request, model_admin, title="Kiểm tra dữ liệu trước khi nhập", rows=rows, token=token,
                filename=data["filename"], mode=mode, summary=importer.summarize(rows, mode),
                summary_json={m: importer.summarize(rows, m) for m in ("new", "update")})


def import_upload(request, model_admin):
    """Bước 1: tải file → kiểm tra → lưu tạm trong phiên → bảng xem trước. Bước 2 (POST có token): xác nhận."""
    if not model_admin.has_add_permission(request):
        raise PermissionDenied
    if request.method == "POST" and request.POST.get("token"):
        return import_confirm(request, model_admin)
    form = ImportUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        f = form.cleaned_data["file"]
        mode = form.cleaned_data["mode"]
        parsed = importer.parse_workbook(f, mode)
        if parsed["errors"]:
            for e in parsed["errors"]:
                form.add_error("file", e)
        else:
            for k in [k for k in request.session.keys() if k.startswith(SESSION_PREFIX)]:
                del request.session[k]
            token = secrets.token_urlsafe(16)
            data = {"filename": f.name, "rows": parsed["rows"]}
            request.session[SESSION_PREFIX + token] = json.loads(json.dumps(data))
            return TemplateResponse(request, "admin/heritage/ditich/import_preview.html",
                                    _preview_ctx(request, model_admin, data, token, mode))
    return TemplateResponse(request, "admin/heritage/ditich/import.html", _ctx(
        request, model_admin, form=form, columns=importer.COLUMNS, example_code=importer.EXAMPLE_CODE))


def import_confirm(request, model_admin):
    token = request.POST.get("token", "")
    data = request.session.get(SESSION_PREFIX + token)
    if not data:
        messages.error(request, "Phiên nhập đã hết hạn hoặc đã được xác nhận. Hãy tải file lên lại.")
        return redirect("admin:heritage_ditich_import")
    mode = request.POST.get("mode")
    if mode not in ("new", "update"):
        messages.error(request, "Hãy chọn “Thêm mới” hoặc “Cập nhật theo mã”.")
        return TemplateResponse(request, "admin/heritage/ditich/import_preview.html",
                                _preview_ctx(request, model_admin, data, token, "new"))
    if mode == "update" and not model_admin.has_change_permission(request):
        raise PermissionDenied
    rows = data["rows"]
    result = importer.apply_rows(rows, mode, user=request.user)
    del request.session[SESSION_PREFIX + token]
    from core.signals import log
    invalid = importer.summarize(rows, mode)["invalid"]
    log("import", changes={k: v[:200] for k, v in result.items()},
        repr_=f"Nhập Excel “{data['filename']}” ({'cập nhật theo mã' if mode == 'update' else 'thêm mới'}): "
              f"thêm {len(result['created'])}, cập nhật {len(result['updated'])}, bỏ qua {len(result['skipped'])}, "
              f"dòng lỗi {invalid}")
    msg = f"Đã nhập xong: thêm mới {len(result['created'])} di tích (trạng thái Nháp)"
    if result["updated"]:
        msg += f", cập nhật {len(result['updated'])}"
    if result["skipped"]:
        msg += f", bỏ qua {len(result['skipped'])} mã đã có ({', '.join(result['skipped'][:10])})"
    if invalid:
        msg += f"; {invalid} dòng lỗi không được nhập"
    messages.success(request, msg + ".")
    codes = result["created"] + result["updated"]
    ids = list(DiTich.objects.filter(ma__in=codes).values_list("id", flat=True)[:300])
    url = reverse("admin:heritage_ditich_changelist")
    return redirect(url + ("?id__in=" + ",".join(map(str, ids)) if ids else ""))


def publish_rights(request):
    return can_publish(request.user)
