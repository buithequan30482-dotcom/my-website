"""Xuất báo cáo Excel với biểu đồ gốc của Excel (XlsxWriter).

Chế độ constant_memory: mỗi sheet ghi tuần tự từng dòng để giữ bộ nhớ thấp khi có hàng chục nghìn bản ghi.
"""
import os
import tempfile
from datetime import date, datetime

import xlsxwriter
from django.utils import timezone

from core.models import SiteConfig

from . import services as sv

# Bảng màu nhận diện
NGOC, NGOC_DAM, SON, DONG, DONG_CHU = "#0E6B6B", "#0A4A4E", "#A3302A", "#B8893A", "#84601F"
GIAY, MUC, DA = "#F6F0E4", "#2B2620", "#6F675B"
MAU_NHOM = [NGOC, DONG, SON, DA, NGOC_DAM]
FONT = "Arial"


class _Fmt:
    """Bộ định dạng dùng chung."""

    def __init__(self, wb):
        base = {"font_name": FONT, "font_size": 10, "font_color": MUC, "valign": "vcenter"}

        def f(**k):
            return wb.add_format({**base, **k})

        self.title = f(bold=True, font_size=15, font_color=NGOC_DAM)
        self.sub = f(italic=True, font_color=DA)
        self.label = f(bold=True, font_color=DA)
        self.text = f()
        self.wrap = f(text_wrap=True, valign="top")
        self.section = f(bold=True, font_size=11, font_color=NGOC_DAM, bottom=2, bottom_color=DONG)
        self.head = f(bold=True, font_color="#FFFFFF", bg_color=NGOC, border=1, border_color=NGOC_DAM,
                      text_wrap=True, align="center")
        self.cell = f(border=1, border_color="#D9D1C1")
        self.cell_wrap = f(border=1, border_color="#D9D1C1", text_wrap=True, valign="top")
        self.int = f(border=1, border_color="#D9D1C1", num_format="#,##0")
        self.dec = f(border=1, border_color="#D9D1C1", num_format="0.00")
        self.dec1 = f(border=1, border_color="#D9D1C1", num_format="0.0")
        self.pct = f(border=1, border_color="#D9D1C1", num_format='+0.0"%";-0.0"%";0.0"%"')
        self.date = f(border=1, border_color="#D9D1C1", num_format="dd/mm/yyyy", align="center")
        self.dt = f(border=1, border_color="#D9D1C1", num_format="dd/mm/yyyy hh:mm", align="center")
        self.note = f(italic=True, font_size=9, font_color=DA)
        self.na = f(border=1, border_color="#D9D1C1", align="center", font_color=DA)
        self.kpi_name = f(border=1, border_color="#D9D1C1", bold=True, bg_color=GIAY)


def _ten_nguoi(user):
    full = (user.get_full_name() or "").strip()
    return f"{full} ({user.username})" if full else user.username


def ten_file(bl):
    return f"BaoCao_TuongTac_DiTichVanDon_{bl.tu:%Y%m%d}_{bl.den:%Y%m%d}.xlsx"


def _chart(wb, kind, title, subtype=None, x_title=None, y_title=None):
    ch = wb.add_chart({"type": kind, **({"subtype": subtype} if subtype else {})})
    ch.set_title({"name": title, "name_font": {"name": FONT, "size": 12, "bold": True, "color": NGOC_DAM}})
    axis_font = {"name": FONT, "size": 9, "color": DA}
    ch.set_x_axis({"num_font": axis_font, "line": {"color": "#D9D1C1"},
                   **({"name": x_title, "name_font": axis_font} if x_title else {})})
    ch.set_y_axis({"num_font": axis_font, "major_gridlines": {"visible": True, "line": {"color": "#ECE5D6"}},
                   "line": {"none": True}, **({"name": y_title, "name_font": axis_font} if y_title else {})})
    ch.set_legend({"position": "bottom", "font": {"name": FONT, "size": 9, "color": MUC}})
    ch.set_chartarea({"border": {"color": "#D9D1C1"}})
    return ch


def _bang(ws, fmt, row, cols, rows, widths=None):
    """Ghi bảng: cols = [(nhãn, khóa, format)], trả về dòng kế tiếp."""
    for c, (nhan, _k, _f) in enumerate(cols):
        ws.write(row, c, nhan, fmt.head)
    for r in rows:
        row += 1
        for c, (_n, k, f) in enumerate(cols):
            v = r.get(k) if isinstance(r, dict) else r[c]
            if v is None or v == "":
                ws.write_blank(row, c, None, f)
            elif isinstance(v, datetime):
                ws.write_datetime(row, c, v, f)
            elif isinstance(v, date):
                ws.write_datetime(row, c, datetime.combine(v, datetime.min.time()), f)
            else:
                ws.write(row, c, v if isinstance(v, (int, float)) else str(v), f)
    return row + 1


def _in_an(ws):
    """Thiết lập in: khổ A4 ngang, vừa 1 trang chiều ngang."""
    ws.set_landscape()
    ws.set_paper(9)
    ws.fit_to_pages(1, 0)
    ws.set_margins(left=0.4, right=0.4, top=0.5, bottom=0.5)


def _sheet_chi_tiet(wb, fmt, ten, cols, gen, widths):
    """Sheet dữ liệu chi tiết: header, freeze, autofilter."""
    ws = wb.add_worksheet(ten)
    _in_an(ws)
    ws.repeat_rows(0)
    ws.hide_gridlines(2)
    ws.freeze_panes(1, 0)
    for c, w in enumerate(widths):
        ws.set_column(c, c, w)
    ws.set_row(0, 30)
    n = _bang(ws, fmt, 0, cols, gen) - 1
    ws.autofilter(0, 0, max(n, 1), len(cols) - 1)
    return ws, n


def xay_dung(bl, user, path):
    """Ghi workbook ra `path`. Trả về số dòng chi tiết đã xuất (để ghi nhật ký)."""
    wb = xlsxwriter.Workbook(path, {"constant_memory": True, "default_date_format": "dd/mm/yyyy",
                                    "strings_to_formulas": False, "strings_to_urls": False})
    wb.set_properties({"title": "Báo cáo tương tác – Website di tích Vân Đồn", "author": _ten_nguoi(user),
                       "company": SiteConfig.get().owner_name})
    fmt = _Fmt(wb)
    th = sv.tong_hop(bl)
    ngay = sv.luot_xem_theo_ngay(bl)
    ds_dt = sv.bang_di_tich(bl)
    S_NGAY, S_DT = "Lượt xem theo ngày", "Theo di tích"

    # ------------------------------------------------------------ Tổng quan
    ws = wb.add_worksheet("Tổng quan")
    ws.hide_gridlines(2)
    _in_an(ws)
    ws.set_column(0, 0, 30)
    ws.set_column(1, 5, 13)
    ws.set_column(6, 6, 3)
    ws.set_column(7, 17, 9)
    cfg = SiteConfig.get()
    ws.set_row(0, 24)
    ws.write(0, 0, "BÁO CÁO TƯƠNG TÁC – WEBSITE DI TÍCH ĐẶC KHU VÂN ĐỒN", fmt.title)
    thong_tin = [
        ("Đơn vị", cfg.owner_name),
        ("Kỳ báo cáo", f"{bl.tu:%d/%m/%Y} – {bl.den:%d/%m/%Y} ({bl.so_ngay} ngày)"),
        ("Kỳ so sánh", "{0:%d/%m/%Y} – {1:%d/%m/%Y}".format(bl.ky_truoc().tu, bl.ky_truoc().den)),
        ("Bộ lọc", bl.mo_ta()),
        ("Người xuất", _ten_nguoi(user)),
        ("Thời điểm xuất", f"{timezone.localtime():%d/%m/%Y %H:%M}"),
        ("Nguồn số liệu", "Trích xuất trực tiếp từ cơ sở dữ liệu website tại thời điểm xuất; không ước tính."),
    ]
    for i, (k, v) in enumerate(thong_tin, start=1):
        ws.write(i, 0, k, fmt.label)
        ws.write(i, 1, v, fmt.text)

    r = len(thong_tin) + 2
    ws.write(r, 0, "1. Chỉ số chính", fmt.section)
    r += 1
    ws.set_row(r, 30)
    for c, h in enumerate(["Chỉ số", "Kỳ này", "Kỳ trước", "Thay đổi"]):
        ws.write(r, c, h, fmt.head)
    ws.merge_range(r, 4, r, 5, "Cách tính", fmt.head)
    for k in th["kpi"]["ds"]:
        r += 1
        f_val = fmt.dec if k["key"] == "diem_tb" else fmt.dec1 if k["don_vi"] in ("%", "ngày") else fmt.int
        ws.write(r, 0, f"{k['nhan']} ({k['don_vi']})", fmt.kpi_name)
        for c, v in ((1, k["gia_tri"]), (2, k["ky_truoc"])):
            ws.write(r, c, v, f_val) if v is not None else ws.write(r, c, "–", fmt.na)
        ws.write(r, 3, k["thay_doi"], fmt.pct) if k["thay_doi"] is not None else ws.write(r, 3, "–", fmt.na)
        ws.merge_range(r, 4, r, 5, k["cach_tinh"], fmt.cell_wrap)
    r += 1
    ws.write(r, 0, "Thay đổi = (Kỳ này − Kỳ trước) / Kỳ trước. “–”: không có dữ liệu hoặc kỳ trước bằng 0.", fmt.note)

    # Bảng góp ý theo loại
    r += 2
    ws.write(r, 0, "2. Góp ý theo loại và trạng thái xử lý", fmt.section)
    r += 1
    gy = th["gop_y_loai"]
    gy_head = r
    for c, h in enumerate(["Loại góp ý"] + [n["nhan"] for n in gy["nhom"]] + ["Tổng"]):
        ws.write(r, c, h, fmt.head)
    for i, nhan in enumerate(gy["nhan"]):
        r += 1
        ws.write(r, 0, nhan, fmt.cell)
        vals = [n["gia_tri"][i] for n in gy["nhom"]]
        for c, v in enumerate(vals, start=1):
            ws.write_number(r, c, v, fmt.int)
        ws.write_number(r, len(vals) + 1, sum(vals), fmt.int)
    gy_last = r

    # Bảng phân bố sao
    r += 2
    ws.write(r, 0, "3. Phân bố số sao (trừ spam)", fmt.section)
    r += 1
    ps = th["phan_bo_sao"]
    ps_head = r
    for c, h in enumerate(["Số sao"] + [n["nhan"] for n in ps["nhom"]] + ["Tổng"]):
        ws.write(r, c, h, fmt.head)
    for i, nhan in enumerate(ps["nhan"]):
        r += 1
        ws.write(r, 0, nhan, fmt.cell)
        vals = [n["gia_tri"][i] for n in ps["nhom"]]
        for c, v in enumerate(vals, start=1):
            ws.write_number(r, c, v, fmt.int)
        ws.write_number(r, len(vals) + 1, sum(vals), fmt.int)
    ps_last = r

    # Biểu đồ 1: lượt xem theo thời gian (dữ liệu ở sheet "Lượt xem theo ngày")
    n_ngay = len(ngay["moc"])
    ch = _chart(wb, "line", "Lượt xem và đánh giá theo ngày")
    ch.add_series({"name": [S_NGAY, 0, 1], "categories": [S_NGAY, 1, 0, n_ngay, 0], "values": [S_NGAY, 1, 1, n_ngay, 1],
                   "line": {"color": NGOC, "width": 2}})
    ch.add_series({"name": [S_NGAY, 0, 2], "categories": [S_NGAY, 1, 0, n_ngay, 0], "values": [S_NGAY, 1, 2, n_ngay, 2],
                   "line": {"color": SON, "width": 1.5}, "y2_axis": True})
    ch.set_x_axis({"date_axis": True, "num_format": "dd/mm", "num_font": {"name": FONT, "size": 8, "color": DA},
                   "major_unit": max(1, n_ngay // 10), "major_unit_type": "days"})
    ch.set_y_axis({"name": "Lượt xem", "name_font": {"name": FONT, "size": 9}, "num_font": {"name": FONT, "size": 9},
                   "major_gridlines": {"visible": True, "line": {"color": "#ECE5D6"}}})
    ch.set_y2_axis({"name": "Đánh giá", "name_font": {"name": FONT, "size": 9}, "num_font": {"name": FONT, "size": 9}})
    ch.set_size({"width": 760, "height": 300})
    ws.insert_chart(1, 7, ch)

    # Biểu đồ 2: góp ý theo loại (cột chồng)
    ch = _chart(wb, "column", "Góp ý theo loại", subtype="stacked")
    for j, nhom in enumerate(gy["nhom"]):
        ch.add_series({"name": ["Tổng quan", gy_head, j + 1], "categories": ["Tổng quan", gy_head + 1, 0, gy_last, 0],
                       "values": ["Tổng quan", gy_head + 1, j + 1, gy_last, j + 1],
                       "fill": {"color": MAU_NHOM[j % len(MAU_NHOM)]}, "gap": 60})
    ch.set_size({"width": 370, "height": 300})
    ws.insert_chart(17, 7, ch)

    # Biểu đồ 3: phân bố sao (cột chồng)
    ch = _chart(wb, "column", "Phân bố số sao", subtype="stacked")
    for j, nhom in enumerate(ps["nhom"]):
        ch.add_series({"name": ["Tổng quan", ps_head, j + 1], "categories": ["Tổng quan", ps_head + 1, 0, ps_last, 0],
                       "values": ["Tổng quan", ps_head + 1, j + 1, ps_last, j + 1],
                       "fill": {"color": MAU_NHOM[j % len(MAU_NHOM)]}, "gap": 60})
    ch.set_size({"width": 380, "height": 300})
    ws.insert_chart(17, 12, ch, {"x_offset": 20})
    ws.activate()

    # ------------------------------------------------------------ Theo di tích
    ws = wb.add_worksheet(S_DT)
    ws.hide_gridlines(2)
    _in_an(ws)
    ws.freeze_panes(1, 2)
    cols = [("Mã", "ma", fmt.cell), ("Tên di tích", "ten", fmt.cell), ("Cấp xếp hạng", "cap", fmt.cell),
            ("Khu vực", "khu_vuc", fmt.cell), ("Lượt xem", "luot_xem", fmt.int),
            ("Số đánh giá", "so_danh_gia", fmt.int), ("Điểm TB (đã duyệt)", "diem_tb", fmt.dec),
            ("Số góp ý", "so_gop_y", fmt.int), ("Muốn đến", "muon_den", fmt.int)]
    for c, w in enumerate([9, 46, 18, 18, 11, 11, 12, 10, 10]):
        ws.set_column(c, c, w)
    ws.set_row(0, 30)
    last = _bang(ws, fmt, 0, cols, ds_dt) - 1
    ws.autofilter(0, 0, max(last, 1), len(cols) - 1)
    # Dữ liệu 2 biểu đồ top 15 đặt ở sheet ẩn "_bieu_do" (constant_memory không cho ghi lại dòng đã qua)
    aux = wb.add_worksheet("_bieu_do")
    aux.hide()
    top_diem = sv.top_diem(bl, 15)[::-1]          # đảo để thanh cao nhất nằm trên cùng
    top_xem = sorted(ds_dt, key=lambda x: x["luot_xem"], reverse=True)[:15][::-1]
    aux.write_row(0, 0, ["Di tích", "Điểm TB", "Di tích", "Lượt xem"])
    for i in range(max(len(top_diem), len(top_xem))):
        if i < len(top_diem):
            aux.write_string(i + 1, 0, f"{top_diem[i]['ma']} {top_diem[i]['ten']}"[:60])
            aux.write_number(i + 1, 1, top_diem[i]["gia_tri"])
        if i < len(top_xem):
            aux.write_string(i + 1, 2, f"{top_xem[i]['ma']} {top_xem[i]['ten']}"[:60])
            aux.write_number(i + 1, 3, top_xem[i]["luot_xem"])

    ch = _chart(wb, "bar", "Điểm trung bình – top 15 di tích")
    if top_diem:
        ch.add_series({"name": "Điểm TB", "categories": ["_bieu_do", 1, 0, len(top_diem), 0],
                       "values": ["_bieu_do", 1, 1, len(top_diem), 1], "fill": {"color": NGOC}, "gap": 40,
                       "data_labels": {"value": True, "num_format": "0.0", "font": {"name": FONT, "size": 8}}})
    ch.set_x_axis({"min": 0, "max": 5, "major_unit": 1, "num_font": {"name": FONT, "size": 8}})
    ch.set_y_axis({"num_font": {"name": FONT, "size": 8, "color": MUC}})
    ch.set_legend({"none": True})
    ch.set_size({"width": 620, "height": 420})
    ws.insert_chart(0, 10, ch)

    ch = _chart(wb, "bar", "Lượt xem – top 15 di tích")
    if top_xem:
        ch.add_series({"name": "Lượt xem", "categories": ["_bieu_do", 1, 2, len(top_xem), 2],
                       "values": ["_bieu_do", 1, 3, len(top_xem), 3], "fill": {"color": DONG}, "gap": 40,
                       "data_labels": {"value": True, "num_format": "#,##0", "font": {"name": FONT, "size": 8}}})
    ch.set_x_axis({"min": 0, "num_format": "#,##0", "num_font": {"name": FONT, "size": 8}})
    ch.set_y_axis({"num_font": {"name": FONT, "size": 8, "color": MUC}})
    ch.set_legend({"none": True})
    ch.set_size({"width": 620, "height": 420})
    ws.insert_chart(22, 10, ch)

    # ------------------------------------------------------------ Chi tiết
    def cot(spec, fmts):
        return [(nhan, k, fmts.get(k, fmt.cell)) for k, nhan in spec]

    f_dg = {"ngay_tao": fmt.dt, "ngay_duyet": fmt.dt, "so_sao": fmt.int, "id": fmt.int, "noi_dung": fmt.cell_wrap,
            "phan_hoi": fmt.cell_wrap}
    _, n_dg = _sheet_chi_tiet(wb, fmt, "Đánh giá chi tiết", cot(sv.COT_DANH_GIA, f_dg), sv.dong_danh_gia(bl),
                              [7, 16, 9, 30, 7, 60, 20, 22, 13, 11, 10, 11, 9, 22, 40, 14, 16])
    f_gy = {"ngay_tao": fmt.dt, "ngay_xu_ly": fmt.dt, "so_ngay_xu_ly": fmt.dec1, "noi_dung": fmt.cell_wrap,
            "phan_hoi": fmt.cell_wrap, "ghi_chu_noi_bo": fmt.cell_wrap}
    _, n_gy = _sheet_chi_tiet(wb, fmt, "Góp ý chi tiết", cot(sv.COT_GOP_Y, f_gy), sv.dong_gop_y(bl),
                              [15, 16, 20, 9, 28, 60, 20, 22, 13, 11, 10, 13, 9, 14, 40, 9, 16, 10, 30])

    # ------------------------------------------------------------ Lượt xem theo ngày
    ws = wb.add_worksheet(S_NGAY)
    ws.hide_gridlines(2)
    _in_an(ws)
    ws.freeze_panes(1, 0)
    ws.set_column(0, 0, 13)
    ws.set_column(1, 2, 14)
    ws.set_row(0, 30)
    rows = [{"ngay": d, "lx": a, "dg": b} for d, a, b in zip(ngay["moc"], ngay["luot_xem"], ngay["danh_gia"])]
    _bang(ws, fmt, 0, [("Ngày", "ngay", fmt.date), ("Lượt xem", "lx", fmt.int),
                       ("Đánh giá (trừ spam)", "dg", fmt.int)], rows)
    ws.autofilter(0, 0, max(len(rows), 1), 2)
    ch = _chart(wb, "line", "Lượt xem theo ngày")
    ch.add_series({"name": [S_NGAY, 0, 1], "categories": [S_NGAY, 1, 0, n_ngay, 0], "values": [S_NGAY, 1, 1, n_ngay, 1],
                   "line": {"color": NGOC, "width": 2}})
    ch.set_x_axis({"date_axis": True, "num_format": "dd/mm", "num_font": {"name": FONT, "size": 8, "color": DA},
                   "major_unit": max(1, n_ngay // 12), "major_unit_type": "days"})
    ch.set_legend({"none": True})
    ch.set_size({"width": 820, "height": 340})
    ws.insert_chart(1, 4, ch)

    wb.close()
    return {"danh_gia": n_dg, "gop_y": n_gy, "di_tich": len(ds_dt), "so_ngay": n_ngay}


def xuat_bytes(bl, user):
    """Tạo file tạm, đọc ra bytes rồi xóa. Trả về (bytes, thống kê)."""
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    try:
        info = xay_dung(bl, user, path)
        with open(path, "rb") as fh:
            return fh.read(), info
    finally:
        os.unlink(path)
