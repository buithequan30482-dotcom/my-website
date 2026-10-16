"""Cổng thông tin công khai (TR mục 5.1)."""
import io
import json

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Prefetch, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET

from core.utils import haversine_km, strip_accents
from interactions.models import TrangThaiDuyet
from interactions.tracking import track

from .models import (CapXepHang, DiemDiTich, DiTich, KhuVuc, LeHoi, LoaiHinh, ThongTinHuuIch, TinTuc, TrangTinh,
                     TuyenThamQuan)

def js(data):
    """JSON an toàn để nhúng trong thẻ <script>."""
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


CAP_STYLE = {"qgdb": "seal-qgdb", "qg": "seal-qg", "tinh": "seal-tinh", "kiemke": "seal-kiemke"}


def _base_qs():
    return (DiTich.objects.published()
            .select_related("khu_vuc", "anh_dai_dien")
            .prefetch_related("loai_hinh", "diem")
            .annotate(sao_tb=Avg("danh_gia__so_sao", filter=Q(danh_gia__trang_thai=TrangThaiDuyet.APPROVED)),
                      so_danh_gia=Count("danh_gia", filter=Q(danh_gia__trang_thai=TrangThaiDuyet.APPROVED), distinct=True)))


def map_points(qs):
    """Dữ liệu điểm cho bản đồ (JSON nhúng vào trang)."""
    pts = []
    for d in qs:
        for p in d.diem.all():
            if p.has_coord:
                pts.append({
                    "lat": p.lat, "lng": p.lng, "name": p.ten, "site": d.ten, "cap": d.cap_xep_hang,
                    "capLabel": d.get_cap_xep_hang_display(), "url": d.get_absolute_url(),
                    "img": d.anh_dai_dien.url(480) if d.anh_dai_dien else "",
                    "main": p.diem_chinh, "ma": d.ma,
                    "dao": d.khu_vuc.dao_vi or "", "daoLabel": (_("Đảo %s") % d.khu_vuc.dao) if d.khu_vuc.dao else "",
                })
    return pts


def home(request):
    track(request)
    qs = _base_qs()
    featured = list(qs.filter(noi_bat=True).order_by("thu_tu")[:6])
    all_sites = list(qs)
    lang = translation.get_language()
    ctx = {
        "featured": featured,
        "routes": TuyenThamQuan.objects.published().select_related("anh_bia").prefetch_related("diem_tuyen__di_tich")[:4],
        "festivals": LeHoi.objects.published().select_related("anh")[:6],
        "travel": ThongTinHuuIch.objects.published().filter(nhom="di_lai")[:4],
        "points_json": js(map_points(all_sites)),
        "counts": {c: sum(1 for d in all_sites if d.cap_xep_hang == c) for c in ("qgdb", "qg", "tinh", "kiemke")},
        "total": len(all_sites),
        "khu_vuc": KhuVuc.objects.all(),
        "lang": lang,
    }
    return render(request, "public/home.html", ctx)


def _filtered(request):
    qs = _base_qs()
    f = {
        "cap": [c for c in request.GET.getlist("cap") if c in CapXepHang.values],
        "loai": request.GET.getlist("loai"),
        "khu": request.GET.getlist("khu"),
        "tq": request.GET.get("tq") == "1",
        "q": (request.GET.get("q") or "").strip()[:100],
        "sort": request.GET.get("sort", "noibat"),
    }
    if f["cap"]:
        qs = qs.filter(cap_xep_hang__in=f["cap"])
    if f["loai"]:
        qs = qs.filter(loai_hinh__slug__in=f["loai"]).distinct()
    if f["khu"]:
        qs = qs.filter(Q(khu_vuc__slug__in=f["khu"]) | Q(khu_vuc_phu__slug__in=f["khu"])).distinct()
    if f["tq"]:
        qs = qs.filter(tham_quan_duoc=True)
    if f["q"]:
        q1, q2 = f["q"].lower(), strip_accents(f["q"])
        qs = qs.filter(Q(search_text__icontains=q1) | Q(search_text__icontains=q2))
    if f["sort"] == "az":
        qs = qs.order_by("ten")
    elif f["sort"] == "danhgia":
        qs = qs.order_by("-sao_tb", "-so_danh_gia", "thu_tu")
    else:
        qs = qs.order_by("thu_tu")
    return qs, f


def site_list(request):
    track(request)
    qs, f = _filtered(request)
    sites = list(qs)
    lat, lng = request.GET.get("lat"), request.GET.get("lng")
    if f["sort"] == "gan" and lat and lng:
        try:
            la, ln = float(lat), float(lng)
            for d in sites:
                p = d.diem_chinh
                d.khoang_cach = haversine_km(la, ln, p.lat, p.lng) if p else 9999
            sites.sort(key=lambda d: d.khoang_cach)
        except ValueError:
            pass
    view = request.GET.get("view", "list")
    page = Paginator(sites, 24).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    ctx = {
        "page": page, "sites": page.object_list, "total": len(sites), "f": f, "view": view,
        "caps": CapXepHang.choices, "loai_list": LoaiHinh.objects.all(), "khu_list": KhuVuc.objects.all(),
        "points_json": js(map_points(sites)),
        "qs_nopage": params.urlencode(),
    }
    return render(request, "public/list.html", ctx)


def site_detail(request, slug):
    d = get_object_or_404(
        DiTich.objects.published().select_related("khu_vuc", "anh_dai_dien")
        .prefetch_related("loai_hinh", "diem", "hinh_anh", "videos", "nguon", "le_hoi"), slug=slug)
    track(request, d)
    reviews = d.danh_gia.filter(trang_thai=TrangThaiDuyet.APPROVED).order_by("-ngay_tao")
    agg = reviews.aggregate(avg=Avg("so_sao"), n=Count("id"))
    dist = {i: 0 for i in range(5, 0, -1)}
    for r in reviews.values("so_sao").annotate(c=Count("id")):
        dist[r["so_sao"]] = r["c"]
    # Di tích lân cận (TR FR-P08)
    near = []
    main = d.diem_chinh
    if main:
        others = DiTich.objects.published().exclude(pk=d.pk).select_related("khu_vuc", "anh_dai_dien").prefetch_related("diem")
        for o in others:
            op = o.diem_chinh
            if op:
                km = haversine_km(main.lat, main.lng, op.lat, op.lng)
                same_island = bool(o.khu_vuc.dao and o.khu_vuc.dao == d.khu_vuc.dao)
                near.append((km, o, same_island))
        near.sort(key=lambda x: x[0])
        near = near[:6]
    lang = translation.get_language() or "vi"
    lang_field = {"vi": "vi", "en": "en", "zh-hans": "zh_hans"}.get(lang, "vi")
    untranslated = lang != "vi" and not getattr(d, f"tom_tat_{lang_field}", "")
    from interactions.models import YeuThich
    points = list(d.diem.all())
    i = 0
    for p in points:
        if p.has_coord:
            p.map_index = i
            i += 1
    gallery = list(d.hinh_anh.all())
    seen, gallery_sources = set(), []
    for h in gallery:
        if h.trang_nguon and h.trang_nguon not in seen:
            seen.add(h.trang_nguon)
            gallery_sources.append(h)
    ctx = {
        "d": d, "points": points, "main": main, "review_form": getattr(request, "review_form", None),
        "points_json": js(map_points([d])),
        "gallery": gallery, "gallery_sources": gallery_sources, "videos": list(d.videos.all()),
        "reviews": reviews[:20], "agg": agg, "dist": dist, "near": near,
        "untranslated": untranslated, "muon_den": YeuThich.objects.filter(di_tich=d).count(),
        "embed_single": len([p for p in d.diem.all() if p.has_coord]) == 1,
        "abs_url": request.build_absolute_uri(d.get_absolute_url()),
    }
    return render(request, "public/detail.html", ctx)


def map_page(request):
    track(request)
    qs, f = _filtered(request)
    ctx = {"points_json": js(map_points(qs)), "f": f,
           "caps": CapXepHang.choices, "loai_list": LoaiHinh.objects.all(), "khu_list": KhuVuc.objects.all()}
    return render(request, "public/map.html", ctx)


def routes(request):
    track(request)
    return render(request, "public/routes.html", {
        "routes": TuyenThamQuan.objects.published().select_related("anh_bia").prefetch_related("diem_tuyen__di_tich__khu_vuc")})


def route_detail(request, slug):
    r = get_object_or_404(TuyenThamQuan.objects.published(), slug=slug)
    track(request)
    stops = list(r.diem_tuyen.select_related("di_tich__anh_dai_dien", "di_tich__khu_vuc").prefetch_related("di_tich__diem"))
    pts = []
    for i, s in enumerate(stops, 1):
        p = s.di_tich.diem_chinh
        if p:
            pts.append({"lat": p.lat, "lng": p.lng, "name": f"{i}. {s.di_tich.ten}", "site": s.di_tich.ten,
                        "cap": s.di_tich.cap_xep_hang, "capLabel": s.di_tich.get_cap_xep_hang_display(),
                        "url": s.di_tich.get_absolute_url(), "order": i, "img": ""})
    return render(request, "public/route_detail.html", {"r": r, "stops": stops, "points_json": js(pts)})


def festivals(request):
    track(request)
    items = LeHoi.objects.published().select_related("anh").prefetch_related("di_tich")
    return render(request, "public/festivals.html", {"items": items})


def useful(request):
    track(request)
    groups = []
    for key, label in ThongTinHuuIch.Nhom.choices:
        items = list(ThongTinHuuIch.objects.published().filter(nhom=key))
        if items:
            groups.append((key, label, items))
    return render(request, "public/useful.html", {"groups": groups})


def news(request):
    track(request)
    page = Paginator(TinTuc.objects.published().select_related("anh"), 12).get_page(request.GET.get("page"))
    return render(request, "public/news.html", {"page": page})


def news_detail(request, slug):
    n = get_object_or_404(TinTuc.objects.published(), slug=slug)
    track(request)
    return render(request, "public/news_detail.html", {"n": n})


def static_page(request, slug):
    p = get_object_or_404(TrangTinh, slug=slug)
    track(request)
    return render(request, "public/page.html", {"p": p})


@require_GET
def suggest(request):
    """Gợi ý tìm kiếm khi gõ (TR FR-P04)."""
    q = (request.GET.get("q") or "").strip()[:60]
    if len(q) < 2:
        return JsonResponse({"items": []})
    q1, q2 = q.lower(), strip_accents(q)
    qs = (DiTich.objects.published().filter(Q(search_text__icontains=q1) | Q(search_text__icontains=q2))
          .select_related("khu_vuc").order_by("thu_tu")[:8])
    return JsonResponse({"items": [{"ten": d.ten, "url": d.get_absolute_url(), "khu": d.khu_vuc.ten,
                                    "cap": d.get_cap_xep_hang_display()} for d in qs]})


def qr_code(request, slug, fmt):
    """Mã QR in tại di tích (TR FR-P13). Quét mở trang theo ngôn ngữ điện thoại (/d/<slug>/)."""
    d = get_object_or_404(DiTich.objects.published(), slug=slug)
    url = request.build_absolute_uri(reverse("short_link", kwargs={"slug": d.slug}))
    if fmt == "svg":
        img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=20, border=2)
        buf = io.BytesIO()
        img.save(buf)
        resp = HttpResponse(buf.getvalue(), content_type="image/svg+xml")
    else:
        qr = qrcode.QRCode(box_size=20, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(url)
        img = qr.make_image(fill_color="#0A4A4E", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        resp = HttpResponse(buf.getvalue(), content_type="image/png")
    if request.GET.get("download"):
        resp["Content-Disposition"] = f'attachment; filename="QR-{d.ma}-{d.slug}.{fmt}"'
    return resp


def short_link(request, slug):
    """Liên kết ngắn cho mã QR: chuyển tới trang theo ngôn ngữ trình duyệt."""
    from django.shortcuts import redirect
    d = get_object_or_404(DiTich.objects.published(), slug=slug)
    lang = translation.get_language_from_request(request, check_path=False)
    with translation.override(lang):
        return redirect(d.get_absolute_url())


def robots(request):
    lines = ["User-agent: *", f"Disallow: /{settings.ADMIN_URL}", "Disallow: /api/",
             f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}"]
    return HttpResponse("\n".join(lines), content_type="text/plain")
