"""Truy vấn thống kê tương tác (TR mục 5.5).

Các hàm ở đây là hàm thuần: nhận `BoLoc`, trả dict/list – dùng chung cho trang thống kê,
xuất Excel và xuất CSV. Mọi phép đếm/tổng đều chạy ở CSDL (aggregate/values).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone

from heritage.models import CapXepHang, DiTich, KhuVuc
from interactions.models import DanhGia, GopY, LuotXem, TrangThaiDuyet, YeuThich

# ---------------------------------------------------------------- nhãn tiếng Việt
KY_CHOICES = [
    ("7", "7 ngày qua"),
    ("30", "30 ngày qua"),
    ("quy", "Quý này"),
    ("nam", "Năm nay"),
    ("tuy_chon", "Tùy chọn"),
]
NGON_NGU = {"vi": "Tiếng Việt", "en": "Tiếng Anh", "zh-hans": "Tiếng Trung"}
THIET_BI = {"mobile": "Điện thoại", "tablet": "Máy tính bảng", "desktop": "Máy tính"}
TRANG_THAI_DG = dict(TrangThaiDuyet.choices)
LOAI_GOP_Y = dict(GopY.Loai.choices)
XU_LY = dict(GopY.XuLy.choices)
CAP = {k: str(v) for k, v in CapXepHang.choices}


def ten_ngon_ngu(code):
    return NGON_NGU.get(code, code or "Không rõ")


def ten_thiet_bi(code):
    return THIET_BI.get(code, code or "Không rõ")


# ---------------------------------------------------------------- bộ lọc
@dataclass
class BoLoc:
    tu: date
    den: date
    ky: str = "30"
    di_tich: int | None = None
    khu_vuc: int | None = None
    cap: str = ""
    ngon_ngu: str = ""
    loi: list = field(default_factory=list)  # thông báo lỗi khi đọc tham số

    @property
    def so_ngay(self):
        return (self.den - self.tu).days + 1

    def ky_truoc(self):
        """Kỳ liền trước, cùng độ dài."""
        den = self.tu - timedelta(days=1)
        return replace(self, tu=den - timedelta(days=self.so_ngay - 1), den=den, loi=[])

    def khoang_thoi_gian(self):
        """(bắt đầu, kết thúc) dạng datetime có múi giờ – để dùng index trên cột ngay_tao."""
        tz = timezone.get_current_timezone()
        return (datetime.combine(self.tu, time.min, tzinfo=tz),
                datetime.combine(self.den + timedelta(days=1), time.min, tzinfo=tz))

    def as_query(self):
        """Tham số GET để giữ nguyên bộ lọc khi chuyển trang/xuất file."""
        q = {"ky": self.ky}
        if self.ky == "tuy_chon":
            q.update(tu=self.tu.isoformat(), den=self.den.isoformat())
        for k in ("di_tich", "khu_vuc", "cap", "ngon_ngu"):
            v = getattr(self, k)
            if v:
                q[k] = v
        return q

    def mo_ta(self):
        """Mô tả bộ lọc bằng lời (in trong báo cáo)."""
        phan = []
        if self.di_tich:
            dt = DiTich.objects.filter(pk=self.di_tich).values_list("ma", "ten").first()
            phan.append(f"Di tích: {dt[0]} – {dt[1]}" if dt else f"Di tích #{self.di_tich}")
        if self.khu_vuc:
            kv = KhuVuc.objects.filter(pk=self.khu_vuc).values_list("ten", flat=True).first()
            phan.append(f"Khu vực: {kv or self.khu_vuc}")
        if self.cap:
            phan.append(f"Cấp xếp hạng: {CAP.get(self.cap, self.cap)}")
        if self.ngon_ngu:
            phan.append(f"Ngôn ngữ: {ten_ngon_ngu(self.ngon_ngu)}")
        return "; ".join(phan) or "Toàn bộ (không lọc)"


def _int_or_none(v):
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _parse_date(v):
    try:
        return date.fromisoformat(v) if v else None
    except ValueError:
        return None


def parse_bo_loc(params, today=None) -> BoLoc:
    """Đọc bộ lọc từ request.GET (hoặc dict). Mặc định 30 ngày qua."""
    today = today or timezone.localdate()
    ky = params.get("ky") or "30"
    loi = []
    if ky == "7":
        tu, den = today - timedelta(days=6), today
    elif ky == "quy":
        thang_dau = (today.month - 1) // 3 * 3 + 1
        tu, den = date(today.year, thang_dau, 1), today
    elif ky == "nam":
        tu, den = date(today.year, 1, 1), today
    elif ky == "tuy_chon":
        tu, den = _parse_date(params.get("tu")), _parse_date(params.get("den"))
        if not tu or not den:
            loi.append("Ngày “từ – đến” không hợp lệ, đang hiển thị 30 ngày qua.")
            ky, tu, den = "30", today - timedelta(days=29), today
        elif tu > den:
            tu, den = den, tu
        if (den - tu).days > 366 * 5:
            loi.append("Khoảng thời gian tối đa 5 năm; đã rút gọn.")
            tu = den - timedelta(days=366 * 5)
    else:
        ky, tu, den = "30", today - timedelta(days=29), today
    cap = params.get("cap") or ""
    if cap not in CAP:
        cap = ""
    ngon_ngu = params.get("ngon_ngu") or ""
    if ngon_ngu not in NGON_NGU:
        ngon_ngu = ""
    return BoLoc(tu=tu, den=den, ky=ky, di_tich=_int_or_none(params.get("di_tich")),
                 khu_vuc=_int_or_none(params.get("khu_vuc")), cap=cap, ngon_ngu=ngon_ngu, loi=loi)


def lua_chon_bo_loc():
    """Danh sách cho các ô chọn của bộ lọc."""
    return {
        "ky": KY_CHOICES,
        "di_tich": list(DiTich.objects.order_by("ma").values_list("pk", "ma", "ten")),
        "khu_vuc": list(KhuVuc.objects.order_by("thu_tu", "ten").values_list("pk", "ten")),
        "cap": list(CAP.items()),
        "ngon_ngu": list(NGON_NGU.items()),
    }


# ---------------------------------------------------------------- queryset đã lọc
def _di_tich_ids(bl: BoLoc):
    """Subquery id di tích theo khu vực (kể cả khu vực phụ) và cấp; None nếu không lọc."""
    if not (bl.khu_vuc or bl.cap or bl.di_tich):
        return None
    qs = DiTich.objects.all()
    if bl.di_tich:
        qs = qs.filter(pk=bl.di_tich)
    if bl.khu_vuc:
        qs = qs.filter(Q(khu_vuc_id=bl.khu_vuc) | Q(khu_vuc_phu=bl.khu_vuc))
    if bl.cap:
        qs = qs.filter(cap_xep_hang=bl.cap)
    return qs.values("pk")


def _loc_chung(qs, bl: BoLoc, co_ngon_ngu=True):
    ids = _di_tich_ids(bl)
    if ids is not None:
        qs = qs.filter(di_tich_id__in=ids)
    if co_ngon_ngu and bl.ngon_ngu:
        qs = qs.filter(ngon_ngu=bl.ngon_ngu)
    return qs


def qs_danh_gia(bl: BoLoc):
    a, b = bl.khoang_thoi_gian()
    return _loc_chung(DanhGia.objects.filter(ngay_tao__gte=a, ngay_tao__lt=b), bl)


def qs_gop_y(bl: BoLoc):
    a, b = bl.khoang_thoi_gian()
    return _loc_chung(GopY.objects.filter(ngay_tao__gte=a, ngay_tao__lt=b), bl)


def qs_luot_xem(bl: BoLoc):
    return _loc_chung(LuotXem.objects.filter(ngay__gte=bl.tu, ngay__lte=bl.den), bl)


def qs_yeu_thich(bl: BoLoc):
    # "Muốn đến" không ghi ngôn ngữ nên bỏ qua bộ lọc ngôn ngữ
    a, b = bl.khoang_thoi_gian()
    return _loc_chung(YeuThich.objects.filter(ngay_tao__gte=a, ngay_tao__lt=b), bl, co_ngon_ngu=False)


# ---------------------------------------------------------------- KPI
def _kpi_mot_ky(bl: BoLoc):
    luot_xem = qs_luot_xem(bl).aggregate(s=Sum("so_luot"))["s"] or 0
    dg = qs_danh_gia(bl).aggregate(
        tong=Count("pk", filter=~Q(trang_thai=TrangThaiDuyet.SPAM)),
        duyet=Count("pk", filter=Q(trang_thai=TrangThaiDuyet.APPROVED)),
        cao=Count("pk", filter=Q(trang_thai=TrangThaiDuyet.APPROVED, so_sao__gte=4)),
        diem=Avg("so_sao", filter=Q(trang_thai=TrangThaiDuyet.APPROVED)),
    )
    gy = qs_gop_y(bl).aggregate(
        tong=Count("pk"),
        da_xl=Count("pk", filter=Q(trang_thai__in=[GopY.XuLy.XONG, GopY.XuLy.DONG])),
        tg=Avg(ExpressionWrapper(F("ngay_xu_ly") - F("ngay_tao"), output_field=DurationField()),
               filter=Q(ngay_xu_ly__isnull=False)),
    )
    muon_den = qs_yeu_thich(bl).count()
    return {
        "luot_xem": luot_xem,
        "so_danh_gia": dg["tong"],
        "diem_tb": round(float(dg["diem"]), 2) if dg["diem"] is not None else None,
        "ti_le_4_5": round(dg["cao"] * 100 / dg["duyet"], 1) if dg["duyet"] else None,
        "gop_y_moi": gy["tong"],
        "ti_le_xu_ly": round(gy["da_xl"] * 100 / gy["tong"], 1) if gy["tong"] else None,
        "tg_xu_ly": round(gy["tg"].total_seconds() / 86400, 1) if gy["tg"] is not None else None,
        "muon_den": muon_den,
    }


# (khóa, nhãn, đơn vị, cách tính) – thứ tự hiển thị
KPI_DINH_NGHIA = [
    ("luot_xem", "Tổng lượt xem", "lượt", "Tổng số lượt xem trang (gộp theo ngày)"),
    ("so_danh_gia", "Số đánh giá", "đánh giá", "Mọi trạng thái, trừ spam"),
    ("diem_tb", "Điểm trung bình", "/5", "Chỉ tính đánh giá đã duyệt"),
    ("ti_le_4_5", "Tỉ lệ 4–5 sao", "%", "Trên tổng đánh giá đã duyệt"),
    ("gop_y_moi", "Góp ý mới", "góp ý", "Góp ý gửi trong kỳ"),
    ("ti_le_xu_ly", "Tỉ lệ góp ý đã xử lý", "%", "(Đã xử lý + Đóng) / tổng góp ý trong kỳ"),
    ("tg_xu_ly", "Thời gian xử lý TB", "ngày", "Từ lúc gửi đến ngày hoàn thành; chỉ góp ý đã hoàn thành"),
    ("muon_den", "Lượt “Muốn đến”", "lượt", "Không áp dụng bộ lọc ngôn ngữ"),
]
# Chỉ số mà giảm là tốt (để tô màu chiều thay đổi)
KPI_GIAM_LA_TOT = {"tg_xu_ly"}


def _phan_tram(nay, truoc):
    if nay is None or truoc in (None, 0):
        return None
    return round((nay - truoc) * 100 / truoc, 1)


def kpi(bl: BoLoc):
    """KPI kỳ này, kỳ trước cùng độ dài và % thay đổi."""
    nay, truoc = _kpi_mot_ky(bl), _kpi_mot_ky(bl.ky_truoc())
    ds = []
    for key, nhan, don_vi, cach_tinh in KPI_DINH_NGHIA:
        pct = _phan_tram(nay[key], truoc[key])
        tot = None
        if pct is not None and pct != 0:
            tot = (pct < 0) if key in KPI_GIAM_LA_TOT else (pct > 0)
        ds.append({"key": key, "nhan": nhan, "don_vi": don_vi, "cach_tinh": cach_tinh,
                   "gia_tri": nay[key], "ky_truoc": truoc[key], "thay_doi": pct, "tot": tot})
    return {"nay": nay, "truoc": truoc, "ds": ds}


# ---------------------------------------------------------------- chuỗi thời gian
def do_chi_tiet(bl: BoLoc):
    """Gom theo ngày; > 92 ngày theo tuần; > 400 ngày theo tháng."""
    if bl.so_ngay > 400:
        return "thang"
    if bl.so_ngay > 92:
        return "tuan"
    return "ngay"


def _cac_moc(bl: BoLoc, muc):
    """Danh sách mốc liên tục (để điền 0 cho ngày trống)."""
    moc = []
    if muc == "ngay":
        d = bl.tu
        while d <= bl.den:
            moc.append(d)
            d += timedelta(days=1)
    elif muc == "tuan":
        d = bl.tu - timedelta(days=bl.tu.weekday())
        while d <= bl.den:
            moc.append(d)
            d += timedelta(days=7)
    else:
        d = bl.tu.replace(day=1)
        while d <= bl.den:
            moc.append(d)
            d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return moc


def _nhan_moc(d, muc):
    if muc == "thang":
        return f"{d.month:02d}/{d.year}"
    if muc == "tuan":
        return f"Tuần {d:%d/%m}"
    return f"{d:%d/%m}"


def _to_date(v):
    return v.date() if isinstance(v, datetime) else v


def chuoi_thoi_gian(bl: BoLoc, muc=None):
    """Lượt xem và số đánh giá (trừ spam) theo ngày/tuần/tháng."""
    muc = muc or do_chi_tiet(bl)
    trunc = {"ngay": None, "tuan": TruncWeek, "thang": TruncMonth}[muc]
    tz = timezone.get_current_timezone()

    lx_qs = qs_luot_xem(bl)
    lx_qs = lx_qs.annotate(m=trunc("ngay") if trunc else F("ngay"))
    lx = {_to_date(r["m"]): r["s"] for r in lx_qs.values("m").annotate(s=Sum("so_luot")).order_by()}

    dg_qs = qs_danh_gia(bl).exclude(trang_thai=TrangThaiDuyet.SPAM)
    dg_qs = dg_qs.annotate(m=(trunc or TruncDate)("ngay_tao", tzinfo=tz))
    dg = {_to_date(r["m"]): r["c"] for r in dg_qs.values("m").annotate(c=Count("pk")).order_by()}

    moc = _cac_moc(bl, muc)
    return {
        "muc": muc,
        "moc": moc,
        "nhan": [_nhan_moc(d, muc) for d in moc],
        "luot_xem": [lx.get(d, 0) for d in moc],
        "danh_gia": [dg.get(d, 0) for d in moc],
    }


# ---------------------------------------------------------------- theo di tích
def top_luot_xem(bl: BoLoc, n=10):
    rows = (qs_luot_xem(bl).filter(di_tich__isnull=False)
            .values("di_tich_id", "di_tich__ma", "di_tich__ten").annotate(s=Sum("so_luot")).order_by("-s")[:n])
    return [{"ma": r["di_tich__ma"], "ten": r["di_tich__ten"], "gia_tri": r["s"]} for r in rows]


def top_diem(bl: BoLoc, n=15):
    rows = (qs_danh_gia(bl).filter(trang_thai=TrangThaiDuyet.APPROVED)
            .values("di_tich_id", "di_tich__ma", "di_tich__ten")
            .annotate(d=Avg("so_sao"), c=Count("pk")).filter(c__gte=1).order_by("-d", "-c")[:n])
    return [{"ma": r["di_tich__ma"], "ten": r["di_tich__ten"], "gia_tri": round(float(r["d"]), 2), "so": r["c"]}
            for r in rows]


def bang_di_tich(bl: BoLoc):
    """Một dòng/di tích: lượt xem, đánh giá, điểm TB, góp ý, muốn đến (5 truy vấn gộp)."""
    dt_qs = DiTich.objects.select_related("khu_vuc").order_by("ma")
    ids = _di_tich_ids(bl)
    if ids is not None:
        dt_qs = dt_qs.filter(pk__in=ids)
    lx = dict(qs_luot_xem(bl).values("di_tich_id").annotate(s=Sum("so_luot")).order_by().values_list("di_tich_id", "s"))
    dg = {r["di_tich_id"]: r for r in qs_danh_gia(bl).values("di_tich_id").annotate(
        c=Count("pk", filter=~Q(trang_thai=TrangThaiDuyet.SPAM)),
        d=Avg("so_sao", filter=Q(trang_thai=TrangThaiDuyet.APPROVED))).order_by()}
    gy = dict(qs_gop_y(bl).values("di_tich_id").annotate(c=Count("pk")).order_by().values_list("di_tich_id", "c"))
    yt = dict(qs_yeu_thich(bl).values("di_tich_id").annotate(c=Count("pk")).order_by().values_list("di_tich_id", "c"))
    out = []
    for d in dt_qs.only("pk", "ma", "ten", "cap_xep_hang", "khu_vuc__ten"):
        r = dg.get(d.pk, {})
        out.append({
            "ma": d.ma, "ten": d.ten, "cap": CAP.get(d.cap_xep_hang, d.cap_xep_hang), "khu_vuc": d.khu_vuc.ten,
            "luot_xem": lx.get(d.pk, 0) or 0, "so_danh_gia": r.get("c", 0) or 0,
            "diem_tb": round(float(r["d"]), 2) if r.get("d") is not None else None,
            "so_gop_y": gy.get(d.pk, 0), "muon_den": yt.get(d.pk, 0),
        })
    return out


# ---------------------------------------------------------------- phân bố
def phan_bo_sao(bl: BoLoc):
    """Số đánh giá theo số sao, tách theo trạng thái (trừ spam)."""
    trang_thai = [TrangThaiDuyet.APPROVED, TrangThaiDuyet.PENDING, TrangThaiDuyet.HIDDEN]
    raw = {(r["so_sao"], r["trang_thai"]): r["c"] for r in qs_danh_gia(bl).exclude(trang_thai=TrangThaiDuyet.SPAM)
           .values("so_sao", "trang_thai").annotate(c=Count("pk")).order_by()}
    return {
        "nhan": [f"{i} sao" for i in range(1, 6)],
        "nhom": [{"key": str(t), "nhan": TRANG_THAI_DG[t], "gia_tri": [raw.get((i, t), 0) for i in range(1, 6)]}
                 for t in trang_thai],
    }


def gop_y_theo_loai(bl: BoLoc):
    raw = {(r["loai"], r["trang_thai"]): r["c"]
           for r in qs_gop_y(bl).values("loai", "trang_thai").annotate(c=Count("pk")).order_by()}
    loai = list(GopY.Loai)
    return {
        "nhan": [l.label for l in loai],
        "nhom": [{"key": str(t), "nhan": t.label, "gia_tri": [raw.get((l, t), 0) for l in loai]}
                 for t in GopY.XuLy],
    }


def luot_xem_theo(bl: BoLoc, truong):
    """Lượt xem theo `ngon_ngu` hoặc `thiet_bi`."""
    ten = ten_ngon_ngu if truong == "ngon_ngu" else ten_thiet_bi
    rows = qs_luot_xem(bl).values(truong).annotate(s=Sum("so_luot")).order_by("-s")
    return {"nhan": [ten(r[truong]) for r in rows], "gia_tri": [r["s"] for r in rows]}


# ---------------------------------------------------------------- việc cần làm (không phụ thuộc kỳ)
def viec_can_lam():
    return {
        "cho_duyet": DanhGia.objects.filter(trang_thai=TrangThaiDuyet.PENDING).count(),
        "gop_y_moi": GopY.objects.filter(trang_thai=GopY.XuLy.MOI).count(),
        "xuong_cap": GopY.objects.filter(loai=GopY.Loai.XUONG_CAP,
                                         trang_thai__in=[GopY.XuLy.MOI, GopY.XuLy.DANG]).count(),
    }


# ---------------------------------------------------------------- tổng hợp cho trang
def tong_hop(bl: BoLoc):
    return {
        "kpi": kpi(bl),
        "chuoi": chuoi_thoi_gian(bl),
        "top_luot_xem": top_luot_xem(bl),
        "top_diem": top_diem(bl),
        "phan_bo_sao": phan_bo_sao(bl),
        "gop_y_loai": gop_y_theo_loai(bl),
        "theo_ngon_ngu": luot_xem_theo(bl, "ngon_ngu"),
        "theo_thiet_bi": luot_xem_theo(bl, "thiet_bi"),
    }


# ---------------------------------------------------------------- dữ liệu chi tiết (xuất file)
def che_email(v):
    """ng***@gmail.com"""
    if not v or "@" not in v:
        return v or ""
    ten, mien = v.split("@", 1)
    return f"{ten[:2]}***@{mien}"


def che_sdt(v):
    """0912***678"""
    v = (v or "").strip()
    if len(v) <= 4:
        return "***" if v else ""
    return f"{v[:4]}***{v[-3:]}" if len(v) > 7 else f"{v[:2]}***{v[-2:]}"


COT_DANH_GIA = [
    ("id", "ID"), ("ngay_tao", "Thời gian gửi"), ("di_tich__ma", "Mã di tích"), ("di_tich__ten", "Tên di tích"),
    ("so_sao", "Số sao"), ("noi_dung", "Nhận xét"), ("ten_hien_thi", "Tên hiển thị"), ("email", "Email"),
    ("dien_thoai", "Điện thoại"), ("ngon_ngu", "Ngôn ngữ"), ("dong_y", "Đồng ý xử lý dữ liệu"),
    ("trang_thai", "Trạng thái"), ("nghi_spam", "Nghi spam"), ("ly_do_nghi", "Lý do nghi"),
    ("phan_hoi", "Phản hồi của BQT"), ("nguoi_duyet__username", "Người duyệt"), ("ngay_duyet", "Ngày duyệt"),
]
COT_GOP_Y = [
    ("ma_tra_cuu", "Mã tra cứu"), ("ngay_tao", "Thời gian gửi"), ("loai", "Loại"), ("di_tich__ma", "Mã di tích"),
    ("di_tich__ten", "Tên di tích"), ("noi_dung", "Nội dung"), ("ho_ten", "Họ tên"), ("email", "Email"),
    ("dien_thoai", "Điện thoại"), ("ngon_ngu", "Ngôn ngữ"), ("dong_y", "Đồng ý xử lý dữ liệu"),
    ("trang_thai", "Trạng thái xử lý"), ("nghi_spam", "Nghi spam"), ("nguoi_xu_ly__username", "Người xử lý"),
    ("phan_hoi", "Phản hồi"), ("cong_khai", "Công khai"), ("ngay_xu_ly", "Ngày hoàn thành"),
    ("so_ngay_xu_ly", "Số ngày xử lý"), ("ghi_chu_noi_bo", "Ghi chú nội bộ"),
]
COT_LUOT_XEM = [
    ("ngay", "Ngày"), ("di_tich__ma", "Mã di tích"), ("di_tich__ten", "Tên di tích"), ("duong_dan", "Đường dẫn"),
    ("ngon_ngu", "Ngôn ngữ"), ("thiet_bi", "Thiết bị"), ("so_luot", "Số lượt"),
]


def _localtime(v):
    return timezone.localtime(v).replace(tzinfo=None) if v else None


def dong_danh_gia(bl: BoLoc):
    """Sinh từng dòng (dict) – đã che email/SĐT, không có ip_hash."""
    keys = [k for k, _ in COT_DANH_GIA]
    for r in qs_danh_gia(bl).order_by("-ngay_tao").values(*keys).iterator(chunk_size=2000):
        r["ngay_tao"], r["ngay_duyet"] = _localtime(r["ngay_tao"]), _localtime(r["ngay_duyet"])
        r["email"], r["dien_thoai"] = che_email(r["email"]), che_sdt(r["dien_thoai"])
        r["trang_thai"] = TRANG_THAI_DG.get(r["trang_thai"], r["trang_thai"])
        r["ngon_ngu"] = ten_ngon_ngu(r["ngon_ngu"])
        r["dong_y"], r["nghi_spam"] = ("Có" if r["dong_y"] else "Không"), ("Có" if r["nghi_spam"] else "")
        r["nguoi_duyet__username"] = r["nguoi_duyet__username"] or ""
        yield r


def dong_gop_y(bl: BoLoc):
    keys = [k for k, _ in COT_GOP_Y if k != "so_ngay_xu_ly"]
    for r in qs_gop_y(bl).order_by("-ngay_tao").values(*keys).iterator(chunk_size=2000):
        tg = (r["ngay_xu_ly"] - r["ngay_tao"]).total_seconds() / 86400 if r["ngay_xu_ly"] else None
        r["so_ngay_xu_ly"] = round(tg, 1) if tg is not None else None
        r["ngay_tao"], r["ngay_xu_ly"] = _localtime(r["ngay_tao"]), _localtime(r["ngay_xu_ly"])
        r["email"], r["dien_thoai"] = che_email(r["email"]), che_sdt(r["dien_thoai"])
        r["loai"] = LOAI_GOP_Y.get(r["loai"], r["loai"])
        r["trang_thai"] = XU_LY.get(r["trang_thai"], r["trang_thai"])
        r["ngon_ngu"] = ten_ngon_ngu(r["ngon_ngu"])
        r["dong_y"], r["nghi_spam"] = ("Có" if r["dong_y"] else "Không"), ("Có" if r["nghi_spam"] else "")
        r["cong_khai"] = "Có" if r["cong_khai"] else ""
        r["nguoi_xu_ly__username"] = r["nguoi_xu_ly__username"] or ""
        r["di_tich__ma"], r["di_tich__ten"] = r["di_tich__ma"] or "", r["di_tich__ten"] or ""
        yield r


def dong_luot_xem(bl: BoLoc):
    keys = [k for k, _ in COT_LUOT_XEM]
    for r in qs_luot_xem(bl).order_by("ngay", "duong_dan").values(*keys).iterator(chunk_size=5000):
        r["ngon_ngu"], r["thiet_bi"] = ten_ngon_ngu(r["ngon_ngu"]), ten_thiet_bi(r["thiet_bi"])
        r["di_tich__ma"], r["di_tich__ten"] = r["di_tich__ma"] or "", r["di_tich__ten"] or ""
        yield r


def luot_xem_theo_ngay(bl: BoLoc):
    """Bảng lượt xem từng ngày (không gom tuần/tháng) – cho sheet "Lượt xem theo ngày"."""
    return chuoi_thoi_gian(bl, muc="ngay")

