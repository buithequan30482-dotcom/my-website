"""Nạp dữ liệu ban đầu: 44 di tích (file Word chuẩn), nội dung 3 ngôn ngữ, tuyến, lễ hội,
thông tin hữu ích, trang tĩnh, nhóm quyền và ảnh minh họa tạm.

Chạy:  python manage.py load_vandon            (bỏ qua bản ghi đã có)
       python manage.py load_vandon --update   (ghi đè nội dung theo file seed)
"""
import json
from pathlib import Path

from django.contrib.auth.models import Group, Permission
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import HelpArticle, SiteConfig
from core.utils import vn_slugify
from heritage.models import (DiemDiTich, DiemTuyen, DiTich, DoTinCay, HinhAnh, KhuVuc, LeHoi, LoaiHinh,
                             NguonThamKhao, ThongTinHuuIch, TrangThai, TrangTinh, TuyenThamQuan, Video)
from heritage.placeholder import make_placeholder, motif_for

SEED = Path(__file__).resolve().parents[3] / "seed"
LANG = {"vi": "vi", "en": "en", "zh": "zh_hans"}

KHU_VUC = [  # (tên, là đảo, tên đảo)
    ("Cái Rồng", False, "Cái Bầu"), ("Đông Xá", False, "Cái Bầu"), ("Hạ Long", False, "Cái Bầu"),
    ("Vạn Yên", False, "Cái Bầu"), ("Đoàn Kết", False, "Cái Bầu"), ("Bản Sen", True, "Trà Bản"),
    ("Minh Châu", True, "Quan Lạn"), ("Quan Lạn", True, "Quan Lạn"), ("Thắng Lợi", True, "Thắng Lợi"),
    ("Ngọc Vừng", True, "Ngọc Vừng"),
]
LOAI = ["Lịch sử", "Kiến trúc nghệ thuật", "Khảo cổ", "Danh lam thắng cảnh"]
CAP = {"Quốc gia đặc biệt": "qgdb", "Quốc gia": "qg", "Cấp tỉnh": "tinh", "Kiểm kê": "kiemke"}

# Điểm con chưa có tọa độ trong danh mục (TR Phụ lục B)
EXTRA_POINTS = {
    "VD01": ["Bến Cái Làng", "Đình Quan Lạn", "Chùa Quan Lạn", "Miếu thờ 3 anh em họ Phạm", "Nghè Trần Khánh Dư",
             "Giếng Chổi", "Miếu Lòng Dinh", "Sông Mang"],
    "VD02": ["Miếu Sao Ỏn"],
}
KNOWN_BAD = {("VD07", "Động Đông Trong"): "Tọa độ trong danh mục nằm giữa làng Quan Lạn, cách đền ~21,9 km – đã ẩn, chờ xác minh.",
             ("VD38", None): "Trùng tọa độ Bảo Tháp (VD01) – chờ xác minh.",
             ("VD23", None): "Trùng tọa độ Đền Trấn Hải (VD11) – chờ xác minh.",
             ("VD11", None): "Trùng tọa độ Miếu Cổng Bà (VD23) – chờ xác minh."}

ROLES = {
    "Biên tập viên": [("heritage", m, a) for m in ("ditich", "diemditich", "hinhanh", "video", "nguonthamkhao",
                                                   "tuyenthamquan", "diemtuyen", "lehoi", "thongtinhuuich", "tintuc", "trangtinh")
                      for a in ("view", "add", "change")] + [("heritage", "hinhanh", "delete"), ("heritage", "video", "delete"),
                                                ("heritage", "nguonthamkhao", "delete"), ("heritage", "diemditich", "delete")],
    "Duyệt nội dung": [("heritage", m, a) for m in ("ditich", "diemditich", "hinhanh", "video", "nguonthamkhao",
                                                    "tuyenthamquan", "diemtuyen", "lehoi", "thongtinhuuich", "tintuc", "trangtinh")
                       for a in ("view", "add", "change", "delete")] + [("heritage", "ditich", "publish")],
    "Kiểm duyệt tương tác": [("interactions", m, a) for m in ("danhgia", "gopy", "tucam") for a in ("view", "change")]
                            + [("heritage", "ditich", "view")],
}


def setl(obj, field, d):
    """Gán trường đa ngôn ngữ từ dict {vi,en,zh}."""
    if isinstance(d, str):
        setattr(obj, f"{field}_vi", d)
        setattr(obj, field, d)
        return
    for k, v in (d or {}).items():
        if k in LANG and v is not None:
            setattr(obj, f"{field}_{LANG[k]}", v)
    if (d or {}).get("vi"):
        setattr(obj, field, d["vi"])


class Command(BaseCommand):
    help = "Nạp dữ liệu di tích Vân Đồn ban đầu"

    def add_arguments(self, p):
        p.add_argument("--update", action="store_true", help="Ghi đè nội dung đã có")
        p.add_argument("--no-images", action="store_true", help="Không tạo ảnh minh họa")

    @transaction.atomic
    def handle(self, *a, update=False, no_images=False, **kw):
        base = json.loads((SEED / "di_tich_chuan.json").read_text("utf-8"))
        content = {c["ma"]: c for f in ("content_ranked.json", "content_kiemke.json")
                   if (SEED / f).exists() for c in json.loads((SEED / f).read_text("utf-8"))}
        misc = json.loads((SEED / "content_misc.json").read_text("utf-8")) if (SEED / "content_misc.json").exists() else {}
        media = json.loads((SEED / "media.json").read_text("utf-8")) if (SEED / "media.json").exists() else {}

        cfg = SiteConfig.get()
        if not cfg.owner_name_en:
            cfg.owner_name_vi = cfg.owner_name_vi or "Phòng Văn hóa – Xã hội, Đặc khu Vân Đồn"
            cfg.owner_name_en = "Culture and Social Affairs Office, Vân Đồn Special Zone"
            cfg.owner_name_zh_hans = "云屯特区文化社会处"
            cfg.site_name_en, cfg.site_name_zh_hans = "Vân Đồn Heritage", "云屯遗迹"
            cfg.save()
        kv = {}
        for i, (ten, la_dao, dao) in enumerate(KHU_VUC):
            o, _ = KhuVuc.objects.get_or_create(slug=vn_slugify(ten), defaults={"ten": ten, "la_dao": la_dao, "dao": dao, "thu_tu": i})
            setl(o, "ten", {"vi": ten, **misc.get("khu_vuc", {}).get(ten, {})})
            setl(o, "dao", dao)
            o.la_dao, o.thu_tu = la_dao, i
            o.save()
            kv[ten] = o
        lh = {}
        for i, ten in enumerate(LOAI):
            o, _ = LoaiHinh.objects.get_or_create(slug=vn_slugify(ten), defaults={"ten": ten, "thu_tu": i})
            setl(o, "ten", {"vi": ten, **misc.get("loai_hinh", {}).get(ten, {})})
            o.save()
            lh[ten] = o

        n_new = 0
        for idx, row in enumerate(base):
            ma = row["ma"]
            c = content.get(ma, {})
            obj = DiTich.objects.filter(ma=ma).first()
            if obj and not update:
                continue
            is_new = obj is None
            obj = obj or DiTich(ma=ma)
            areas = [x.strip() for x in row["khu_vuc"].split(",") if x.strip()]
            obj.khu_vuc = kv[areas[0]]
            obj.cap_xep_hang = CAP[row["cap"]]
            setl(obj, "ten", c.get("ten") or row["ten"])
            obj.ten_khac = c.get("ten_khac", "")
            obj.dia_chi_cu = row["dc_cu"]
            setl(obj, "dia_chi_moi", {"vi": row["dc_moi"]})
            for f in ("tom_tat", "noi_dung", "thong_tin_tham_quan", "gio_mo_cua", "hien_trang_mo_ta"):
                if c.get(f):
                    setl(obj, f, c[f])
            if not obj.tom_tat:
                setl(obj, "tom_tat", {"vi": f"{row['ten']} – di tích {row['cap'].lower()} tại {row['dc_moi']}."})
            setl(obj, "phi_tham_quan", {"vi": "Miễn phí", "en": "Free", "zh": "免费"})
            obj.hien_trang = c.get("hien_trang") or "tot"
            obj.tham_quan_duoc = c.get("tham_quan_duoc", True)
            obj.so_quyet_dinh = c.get("so_quyet_dinh", "")
            obj.co_quan_qd = c.get("co_quan_qd", "")
            obj.nam_xep_hang = c.get("nam_xep_hang") or None
            obj.dien_tich = c.get("dien_tich", "")
            obj.noi_bat = bool(c.get("noi_bat")) or obj.cap_xep_hang in ("qgdb", "qg")
            obj.thu_tu = {"qgdb": 1, "qg": 10, "tinh": 20, "kiemke": 50}[obj.cap_xep_hang] + idx
            obj.trang_thai = TrangThai.DRAFT if is_new else obj.trang_thai
            obj.save()
            # loại hình
            loai = row["loai"].lower()
            sel = []
            if "lịch sử" in loai or "lich su" in loai:
                sel.append(lh["Lịch sử"])
            if "kiến trúc" in loai:
                sel.append(lh["Kiến trúc nghệ thuật"])
            if "khảo cổ" in loai:
                sel.append(lh["Khảo cổ"])
            if "danh" in loai or "dltc" in loai:
                sel.append(lh["Danh lam thắng cảnh"])
            obj.loai_hinh.set(sel or [lh["Lịch sử"]])
            obj.khu_vuc_phu.set([kv[x] for x in areas[1:]])
            # điểm
            obj.diem.all().delete()
            dn = c.get("diem_ten", {})
            pts = row["diem"] or []
            for j, p in enumerate(pts):
                d = DiemDiTich(di_tich=obj, thu_tu=j, toa_do_goc=p["dms"], diem_chinh=(j == 0))
                setl(d, "ten", {"vi": p["ten"], **dn.get(p["ten"], {})})
                bad = KNOWN_BAD.get((ma, p["ten"])) or KNOWN_BAD.get((ma, None))
                if (ma, p["ten"]) in KNOWN_BAD:
                    d.vi_do = d.kinh_do = None
                    d.do_tin_cay = DoTinCay.CHUA
                    d.mo_ta = bad
                    d.diem_chinh = False
                else:
                    d.vi_do, d.kinh_do = p["lat"], p["lng"]
                    d.do_tin_cay = DoTinCay.TUONG_DOI if p["tuong_doi"] else DoTinCay.DANH_MUC
                    if bad:
                        d.do_tin_cay = DoTinCay.CHUA
                        d.mo_ta = bad
                d.save()
            for k, ten in enumerate(EXTRA_POINTS.get(ma, [])):
                d = DiemDiTich(di_tich=obj, thu_tu=len(pts) + k, do_tin_cay=DoTinCay.CHUA)
                setl(d, "ten", {"vi": ten, **dn.get(ten, {})})
                d.save()
            if not pts and ma not in EXTRA_POINTS:
                d = DiemDiTich(di_tich=obj, do_tin_cay=DoTinCay.CHUA, diem_chinh=True)
                setl(d, "ten", c.get("ten") or {"vi": row["ten"]})
                d.save()
            # nguồn
            obj.nguon.all().delete()
            for k, s in enumerate(c.get("nguon", [])):
                NguonThamKhao.objects.create(di_tich=obj, ten=s.get("ten", "")[:400], url=(s.get("url") or "")[:500],
                                             ngay=s.get("ngay", "")[:50], thu_tu=k)
            # ảnh, video thật từ seed/media.json (ảnh dạng liên kết ngoài – xem HinhAnh.url_ngoai)
            m = media.get(ma) or {}
            if m.get("anh"):
                obj.hinh_anh.filter(la_minh_hoa=True).delete()
                dai_dien = None
                for k, a in enumerate(m["anh"]):
                    h = obj.hinh_anh.filter(url_ngoai=a["url"]).first() or HinhAnh(di_tich=obj, url_ngoai=a["url"])
                    h.trang_nguon = a.get("trang_nguon", "")[:500]
                    h.nguon = a.get("nguon", "")[:300]
                    h.tac_gia = a.get("tac_gia", "")[:200]
                    h.thu_tu = k + 1
                    setl(h, "chu_thich", a.get("chu_thich") or {})
                    h.save()
                    if dai_dien is None or a.get("dai_dien"):
                        dai_dien = h
                obj.anh_dai_dien = dai_dien
            for k, v in enumerate(m.get("video", [])):
                vo = obj.videos.filter(youtube_url=v["youtube_url"]).first() or Video(di_tich=obj, youtube_url=v["youtube_url"])
                setl(vo, "tieu_de", v.get("tieu_de") or {})
                vo.nguon = v.get("nguon", "")[:300]
                vo.thu_tu = k + 1
                vo.save()
            # ảnh minh họa
            if not no_images and not obj.hinh_anh.exists():
                data = make_placeholder(obj.ten_vi or obj.ten, motif_for(obj.ten_vi or obj.ten, row["loai"]), seed=idx)
                h = HinhAnh(di_tich=obj, nguon="Ảnh minh họa do hệ thống tạo – cần thay ảnh chính thức", la_minh_hoa=True)
                setl(h, "chu_thich", {"vi": f"Ảnh minh họa – {obj.ten_vi}", "en": f"Illustration – {obj.ten_en or obj.ten_vi}",
                                      "zh": f"示意图 – {obj.ten_zh_hans or obj.ten_vi}"})
                h.tep.save(f"{vn_slugify(obj.ten_vi)}-minh-hoa.jpg", ContentFile(data), save=False)
                h.save()
                obj.anh_dai_dien = HinhAnh.objects.get(pk=h.pk)
            if not obj.anh_dai_dien_id and obj.hinh_anh.exists():
                obj.anh_dai_dien = obj.hinh_anh.first()
            if is_new:
                obj.trang_thai = TrangThai.PUBLISHED if not obj.missing_for_publish() else TrangThai.DRAFT
            obj.save()
            n_new += 1
        self.stdout.write(self.style.SUCCESS(f"Di tích đã nạp/cập nhật: {n_new}"))

        dt = {d.ma: d for d in DiTich.objects.all()}
        if update or not TuyenThamQuan.objects.exists():
            TuyenThamQuan.objects.all().delete()
            for i, t in enumerate(misc.get("tuyen", [])):
                o = TuyenThamQuan(thu_tu=i)
                for f in ("ten", "mo_ta", "thoi_luong", "phuong_tien"):
                    setl(o, f, t.get(f, {}))
                o.save()
                for j, p in enumerate(t.get("diem", [])):
                    if p["ma"] in dt:
                        dtu = DiemTuyen(tuyen=o, di_tich=dt[p["ma"]], thu_tu=j)
                        setl(dtu, "ghi_chu", p.get("ghi_chu", {}))
                        dtu.save()
                if o.diem_tuyen.exists():
                    o.anh_bia = o.diem_tuyen.first().di_tich.anh_dai_dien
                    o.save()
        if update or not LeHoi.objects.exists():
            LeHoi.objects.all().delete()
            for l in misc.get("le_hoi", []):
                o = LeHoi(thang_sap_xep=l.get("thang_sap_xep") or 1, nguon=(l.get("nguon") or "")[:400])
                for f in ("ten", "mo_ta", "thoi_gian_am_lich", "thoi_gian_duong_lich", "dia_diem", "cong_nhan"):
                    setl(o, f, l.get(f, {}))
                o.slug = vn_slugify(o.ten_vi)
                o.save()
                o.di_tich.set([dt[m] for m in l.get("di_tich", []) if m in dt])
                first = o.di_tich.first()
                if first:
                    o.anh = first.anh_dai_dien
                    o.save()
        if update or not ThongTinHuuIch.objects.exists():
            ThongTinHuuIch.objects.all().delete()
            for i, t in enumerate(misc.get("thong_tin", [])):
                o = ThongTinHuuIch(nhom=t["nhom"], lien_ket=t.get("lien_ket", "")[:200], nguon=(t.get("nguon") or "")[:400],
                                   thu_tu=i)
                if t.get("ngay_cap_nhat"):
                    o.ngay_cap_nhat = t["ngay_cap_nhat"]
                setl(o, "tieu_de", t["tieu_de"])
                setl(o, "noi_dung", t["noi_dung"])
                o.save()
        for p in misc.get("trang_tinh", []):
            o = TrangTinh.objects.filter(slug=p["slug"]).first()
            if o and not update:
                continue
            o = o or TrangTinh(slug=p["slug"])
            setl(o, "tieu_de", p["tieu_de"])
            setl(o, "noi_dung", p["noi_dung"])
            o.save()

        # Nhóm quyền theo vai trò (TR FR-A01)
        for name, perms in ROLES.items():
            g, _ = Group.objects.get_or_create(name=name)
            objs = []
            for app, model, act in perms:
                code = f"{act}_{model}" if act != "publish" else "publish_ditich"
                p = Permission.objects.filter(content_type__app_label=app, codename=code).first()
                if p:
                    objs.append(p)
            g.permissions.set(objs)
        from core.help_content import load_help
        load_help(update=update)
        self.stdout.write(self.style.SUCCESS("Hoàn tất nạp dữ liệu."))
