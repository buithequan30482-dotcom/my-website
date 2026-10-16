"""Trang thống kê, hàng đợi kiểm duyệt và xuất báo cáo (TR mục 5.5)."""
import csv
from functools import wraps
from urllib.parse import urlencode

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.signals import log
from interactions.models import DanhGia, TrangThaiDuyet

from . import excel, services as sv


def can_quyen(perm="interactions.view_danhgia"):
    """Chỉ nhân viên (staff) có quyền `perm` hoặc quản trị hệ thống."""
    def deco(fn):
        @staff_member_required
        @wraps(fn)
        def inner(request, *a, **k):
            if not (request.user.is_superuser or request.user.has_perm(perm)):
                raise PermissionDenied("Bạn không có quyền thực hiện thao tác này.")
            return fn(request, *a, **k)
        return inner
    return deco


def so_vn(n):
    """Định dạng số nguyên kiểu Việt Nam: 91.827"""
    return f"{n:,}".replace(",", ".") if isinstance(n, int) else n


def _admin_url(name, query=""):
    """URL trang quản trị; None nếu mô hình chưa đăng ký với admin."""
    try:
        return reverse(name) + query
    except NoReverseMatch:
        return None


def _ctx(request, **extra):
    """Ngữ cảnh chung của khu quản trị (tiêu đề, menu…)."""
    return {**admin.site.each_context(request), **extra}


# ---------------------------------------------------------------- trang thống kê
@can_quyen()
def index(request):
    bl = sv.parse_bo_loc(request.GET)
    data = sv.tong_hop(bl)
    viec = sv.viec_can_lam()
    q = urlencode(bl.as_query())
    chart_data = {
        "chuoi": {k: data["chuoi"][k] for k in ("nhan", "luot_xem", "danh_gia")},
        "muc": data["chuoi"]["muc"],
        "top_luot_xem": data["top_luot_xem"],
        "top_diem": data["top_diem"],
        "phan_bo_sao": data["phan_bo_sao"],
        "gop_y_loai": data["gop_y_loai"],
        "theo_ngon_ngu": data["theo_ngon_ngu"],
        "theo_thiet_bi": data["theo_thiet_bi"],
    }
    viec_ds = [
        {"nhan": "Nhận xét chờ duyệt", "so": viec["cho_duyet"], "mau": "ngoc",
         "url": reverse("dashboard:moderation"),
         "url_phu": _admin_url("admin:interactions_danhgia_changelist", "?trang_thai__exact=pending"),
         "nhan_phu": "Mở danh sách quản trị"},
        {"nhan": "Góp ý mới", "so": viec["gop_y_moi"], "mau": "dong",
         "url": _admin_url("admin:interactions_gopy_changelist", "?trang_thai__exact=moi")},
        {"nhan": "Báo di tích xuống cấp chưa xử lý", "so": viec["xuong_cap"], "mau": "son",
         "url": _admin_url("admin:interactions_gopy_changelist", "?loai__exact=xuong_cap&trang_thai__in=moi,dang")},
    ]
    for k in data["kpi"]["ds"]:
        k["so_hien_thi"] = so_vn(k["gia_tri"])
    for v in viec_ds:
        v["so_hien_thi"] = so_vn(v["so"])
    for m in bl.loi:
        messages.warning(request, m)
    return render(request, "dashboard/index.html", _ctx(
        request, title="Thống kê tương tác", bl=bl, lua_chon=sv.lua_chon_bo_loc(), data=data,
        kpi=data["kpi"]["ds"], viec=viec_ds, q=q, chart_data=chart_data,
        ky_truoc=bl.ky_truoc(), co_the_duyet=request.user.has_perm("interactions.change_danhgia"),
    ))


# ---------------------------------------------------------------- hàng đợi kiểm duyệt
@can_quyen()
def moderation(request):
    qs = (DanhGia.objects.filter(trang_thai=TrangThaiDuyet.PENDING).select_related("di_tich")
          .order_by("-nghi_spam", "ngay_tao"))
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(request, "dashboard/moderation.html", _ctx(
        request, title="Kiểm duyệt nhận xét", page=page, tong=page.paginator.count,
        co_the_duyet=request.user.has_perm("interactions.change_danhgia"),
    ))


HANH_DONG = {
    "approve": (TrangThaiDuyet.APPROVED, "Đã duyệt"),
    "hide": (TrangThaiDuyet.HIDDEN, "Đã ẩn"),
    "spam": (TrangThaiDuyet.SPAM, "Đã đánh dấu spam"),
    "reply": (TrangThaiDuyet.APPROVED, "Đã lưu phản hồi và duyệt"),
}


@can_quyen("interactions.change_danhgia")
@require_POST
def moderation_action(request):
    """Nhận `act` dạng "<hành động>:<id>" hoặc "<hành động>:selected" (kèm danh sách `ids`)."""
    act, _, target = (request.POST.get("act") or "").partition(":")
    if act not in HANH_DONG:
        return _ket_qua(request, False, "Thao tác không hợp lệ.", [])
    if target == "selected":
        ids = [int(i) for i in request.POST.getlist("ids") if i.isdigit()]
    else:
        ids = [int(target)] if target.isdigit() else []
    if not ids:
        return _ket_qua(request, False, "Chưa chọn nhận xét nào.", [])

    trang_thai, thong_bao = HANH_DONG[act]
    now = timezone.now()
    xong = []
    # Lưu từng bản ghi qua save() để tín hiệu ghi nhật ký (AuditLog) hoạt động
    for dg in DanhGia.objects.filter(pk__in=ids, trang_thai=TrangThaiDuyet.PENDING):
        fields = ["trang_thai", "nguoi_duyet", "ngay_duyet"]
        if act == "reply":
            phan_hoi = (request.POST.get(f"phan_hoi_{dg.pk}") or "").strip()
            if not phan_hoi:
                continue
            dg.phan_hoi = phan_hoi[:2000]
            fields.append("phan_hoi")
        dg.trang_thai, dg.nguoi_duyet, dg.ngay_duyet = trang_thai, request.user, now
        dg.save(update_fields=fields)
        xong.append(dg.pk)
    if not xong:
        msg = "Hãy nhập nội dung phản hồi." if act == "reply" else "Nhận xét đã được xử lý trước đó."
        return _ket_qua(request, False, msg, [])
    return _ket_qua(request, True, f"{thong_bao} {len(xong)} nhận xét.", xong)


def _ket_qua(request, ok, msg, ids):
    if request.headers.get("x-requested-with") == "fetch":
        return JsonResponse({"ok": ok, "message": msg, "ids": ids,
                             "con_lai": DanhGia.objects.filter(trang_thai=TrangThaiDuyet.PENDING).count()},
                            status=200 if ok else 400)
    (messages.success if ok else messages.warning)(request, msg)
    return redirect(request.POST.get("next") or reverse("dashboard:moderation"))


# ---------------------------------------------------------------- xuất file
@can_quyen()
def export_xlsx(request):
    bl = sv.parse_bo_loc(request.GET)
    data, info = excel.xuat_bytes(bl, request.user)
    ten = excel.ten_file(bl)
    log("export", user=request.user, repr_=(
        f"Xuất báo cáo Excel {bl.tu:%d/%m/%Y}–{bl.den:%d/%m/%Y} ({bl.mo_ta()}): "
        f"{info['danh_gia']} đánh giá, {info['gop_y']} góp ý"))
    resp = HttpResponse(data, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{ten}"'
    return resp


class _Echo:
    def write(self, v):
        return v


CSV_BANG = {
    "danhgia": (sv.COT_DANH_GIA, sv.dong_danh_gia, "DanhGia"),
    "gopy": (sv.COT_GOP_Y, sv.dong_gop_y, "GopY"),
    "luotxem": (sv.COT_LUOT_XEM, sv.dong_luot_xem, "LuotXem"),
}


def _fmt_csv(v):
    if v is None:
        return ""
    if hasattr(v, "strftime"):
        return v.strftime("%d/%m/%Y %H:%M") if hasattr(v, "hour") else v.strftime("%d/%m/%Y")
    return v


@can_quyen()
def export_csv(request):
    bang = request.GET.get("bang", "danhgia")
    if bang not in CSV_BANG:
        bang = "danhgia"
    cot, gen, ten = CSV_BANG[bang]
    bl = sv.parse_bo_loc(request.GET)
    writer = csv.writer(_Echo())

    def rows():
        yield "﻿"  # BOM để Excel nhận đúng UTF-8
        yield writer.writerow([nhan for _, nhan in cot])
        for r in gen(bl):
            yield writer.writerow([_fmt_csv(r.get(k)) for k, _ in cot])

    log("export", user=request.user,
        repr_=f"Xuất CSV {ten} {bl.tu:%d/%m/%Y}–{bl.den:%d/%m/%Y} ({bl.mo_ta()})")
    resp = StreamingHttpResponse(rows(), content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = (
        f'attachment; filename="{ten}_DiTichVanDon_{bl.tu:%Y%m%d}_{bl.den:%Y%m%d}.csv"')
    return resp
