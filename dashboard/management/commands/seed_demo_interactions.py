"""Sinh dữ liệu tương tác DEMO để chụp màn hình trang thống kê. KHÔNG chạy trên production.

Đánh dấu dữ liệu demo:
- Đánh giá: ten_hien_thi bắt đầu "[DEMO]"
- Góp ý: ho_ten bắt đầu "[DEMO]"
- Lượt xem: duong_dan bắt đầu "/__demo__/"
- Muốn đến: ma_trinh_duyet bắt đầu "demo-"

    python3 manage.py seed_demo_interactions            # sinh dữ liệu
    python3 manage.py seed_demo_interactions --clear    # chỉ xóa dữ liệu demo
"""
import random
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from heritage.models import DiTich
from interactions.models import DanhGia, GopY, LuotXem, TrangThaiDuyet, YeuThich

TEN = ["Minh Anh", "Thu Hà", "Quốc Bảo", "Lan Phương", "Đức Thắng", "Hải Yến", "Tuấn Kiệt", "Ngọc Mai",
       "John Smith", "Emma Brown", "李伟", "王芳", "Hoàng Nam", "Thanh Tâm", "Bích Ngọc", "Văn Long"]
NHAN_XET = {
    5: ["Cảnh quan rất đẹp, di tích được giữ gìn tốt.", "Rất đáng đến, hướng dẫn viên nhiệt tình.",
        "Không gian linh thiêng, yên bình. Sẽ quay lại.", "Beautiful place with rich history."],
    4: ["Di tích đẹp, nên có thêm biển chỉ dẫn.", "Đáng tham quan, đường đi hơi khó tìm.",
        "Thông tin trên website hữu ích, đến nơi đúng như mô tả."],
    3: ["Tạm ổn, khu vực xung quanh cần vệ sinh hơn.", "Thiếu bãi đỗ xe, cần cải thiện."],
    2: ["Biển giới thiệu bị mờ, khó đọc.", "Đến nơi đóng cửa dù website ghi mở cửa."],
    1: ["Không có người trông coi, rác nhiều.", "Mua ngay khuyến mãi tại link-quang-cao.example !!!"],
}
GOP_Y = {
    GopY.Loai.DICH_VU: "Đề nghị bố trí thêm nhà vệ sinh công cộng gần khu di tích.",
    GopY.Loai.MONG_MUON: "Mong có thêm bản thuyết minh tiếng Anh và tiếng Trung tại chỗ.",
    GopY.Loai.XUONG_CAP: "Tường bao phía sau có vết nứt, mái ngói một số chỗ bị xô lệch.",
    GopY.Loai.HOI_DAP: "Xin hỏi giờ mở cửa dịp lễ hội và có cần đặt lịch trước không?",
    GopY.Loai.KHAC: "Website tải chậm trên điện thoại ở vùng sóng yếu.",
}
NGON_NGU = [("vi", 70), ("en", 20), ("zh-hans", 10)]
THIET_BI = [("mobile", 62), ("desktop", 30), ("tablet", 8)]


def _chon(pairs):
    return random.choices([p[0] for p in pairs], weights=[p[1] for p in pairs])[0]


class Command(BaseCommand):
    help = "Sinh (hoặc xóa với --clear) dữ liệu tương tác DEMO cho trang thống kê. Không dùng trên production."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Chỉ xóa dữ liệu demo rồi dừng.")
        parser.add_argument("--danh-gia", type=int, default=300)
        parser.add_argument("--gop-y", type=int, default=60)
        parser.add_argument("--ngay", type=int, default=120, help="Số ngày lượt xem (tính lùi từ hôm nay).")
        parser.add_argument("--seed", type=int, default=2025, help="Hạt giống ngẫu nhiên để kết quả lặp lại được.")
        parser.add_argument("--force", action="store_true", help="Cho phép chạy khi DEBUG=False (không khuyến nghị).")

    def handle(self, *args, **o):
        if not settings.DEBUG and not o["force"]:
            raise CommandError("Từ chối chạy khi DEBUG=False. Đây là dữ liệu DEMO, không dùng trên production.")
        with transaction.atomic():
            self._clear()
            if o["clear"]:
                return
            di_tich = list(DiTich.objects.values_list("pk", "slug"))
            if not di_tich:
                raise CommandError("Chưa có di tích nào. Hãy nạp dữ liệu di tích trước.")
            random.seed(o["seed"])
            self._seed(di_tich, o["danh_gia"], o["gop_y"], o["ngay"])

    def _clear(self):
        n = [
            DanhGia.objects.filter(ten_hien_thi__startswith="[DEMO]").delete()[0],
            GopY.objects.filter(ho_ten__startswith="[DEMO]").delete()[0],
            LuotXem.objects.filter(duong_dan__startswith="/__demo__/").delete()[0],
            YeuThich.objects.filter(ma_trinh_duyet__startswith="demo-").delete()[0],
        ]
        self.stdout.write(f"Đã xóa dữ liệu demo cũ: {n[0]} đánh giá, {n[1]} góp ý, {n[2]} dòng lượt xem, {n[3]} muốn đến.")

    def _seed(self, di_tich, so_dg, so_gy, so_ngay):
        now = timezone.now()
        today = timezone.localdate()
        # Mức độ quan tâm khác nhau giữa các di tích
        trong_so = {pk: random.uniform(0.3, 3.0) for pk, _ in di_tich}

        def thoi_diem(max_days):
            return now - timedelta(days=random.uniform(0, max_days), minutes=random.randint(0, 600))

        # --- Lượt xem theo ngày
        lx = []
        for d in range(so_ngay):
            ngay = today - timedelta(days=d)
            mua = 1.6 if ngay.weekday() >= 5 else 1.0          # cuối tuần đông hơn
            for pk, slug in di_tich:
                for nn, w_nn in NGON_NGU:
                    for tb, w_tb in THIET_BI:
                        so = int(random.gauss(14, 4) * trong_so[pk] * mua * w_nn / 100 * w_tb / 100 * 10)
                        if so > 0:
                            lx.append(LuotXem(ngay=ngay, duong_dan=f"/__demo__/{nn}/di-tich/{slug}/", di_tich_id=pk,
                                              ngon_ngu=nn, thiet_bi=tb, so_luot=so))
        LuotXem.objects.bulk_create(lx, batch_size=2000)

        # --- Đánh giá
        dg = []
        ids = [pk for pk, _ in di_tich]
        w = [trong_so[pk] for pk in ids]
        for i in range(so_dg):
            sao = random.choices([5, 4, 3, 2, 1], weights=[45, 30, 12, 8, 5])[0]
            tt = random.choices([TrangThaiDuyet.APPROVED, TrangThaiDuyet.PENDING, TrangThaiDuyet.HIDDEN,
                                 TrangThaiDuyet.SPAM], weights=[72, 15, 7, 6])[0]
            ngay_tao = thoi_diem(so_ngay)
            spam = tt == TrangThaiDuyet.SPAM or (sao == 1 and random.random() < .5)
            dg.append(DanhGia(
                di_tich_id=random.choices(ids, weights=w)[0], so_sao=sao, noi_dung=random.choice(NHAN_XET[sao]),
                ten_hien_thi=f"[DEMO] {random.choice(TEN)}", email=f"demo{i}@example.com" if random.random() < .6 else "",
                ngon_ngu=_chon(NGON_NGU), dong_y=True, trang_thai=tt, nghi_spam=spam,
                ly_do_nghi="Chứa liên kết quảng cáo" if spam else "", ngay_tao=ngay_tao,
                ngay_duyet=ngay_tao + timedelta(hours=random.randint(2, 72)) if tt != TrangThaiDuyet.PENDING else None,
            ))
        DanhGia.objects.bulk_create(dg, batch_size=1000)

        # --- Góp ý (lưu từng bản ghi để sinh mã tra cứu)
        loai_w = [(GopY.Loai.DICH_VU, 25), (GopY.Loai.MONG_MUON, 25), (GopY.Loai.XUONG_CAP, 15),
                  (GopY.Loai.HOI_DAP, 25), (GopY.Loai.KHAC, 10)]
        for i in range(so_gy):
            loai = _chon(loai_w)
            ngay_tao = thoi_diem(so_ngay)
            tuoi = (now - ngay_tao).days
            tt = random.choices(list(GopY.XuLy), weights=[15, 20, 50, 15] if tuoi > 14 else [55, 30, 12, 3])[0]
            xong = ngay_tao + timedelta(days=random.uniform(.5, 12)) if tt in (GopY.XuLy.XONG, GopY.XuLy.DONG) else None
            GopY(loai=loai, di_tich_id=random.choice(ids) if loai != GopY.Loai.KHAC else None,
                 noi_dung=GOP_Y[loai], ho_ten=f"[DEMO] {random.choice(TEN)}", email=f"gopy{i}@example.com",
                 dien_thoai=f"09{random.randint(10000000, 99999999)}", ngon_ngu=_chon(NGON_NGU), dong_y=True,
                 trang_thai=tt, ngay_tao=ngay_tao, ngay_xu_ly=min(xong, now) if xong else None).save()

        # --- Muốn đến
        yt = []
        for pk in ids:
            for j in range(int(random.uniform(3, 25) * trong_so[pk])):
                yt.append(YeuThich(di_tich_id=pk, ma_trinh_duyet=f"demo-{pk}-{j}", ngay_tao=thoi_diem(so_ngay)))
        YeuThich.objects.bulk_create(yt, batch_size=2000, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS(
            f"Đã sinh DEMO cho {len(ids)} di tích: {len(dg)} đánh giá, {so_gy} góp ý, "
            f"{len(lx)} dòng lượt xem ({so_ngay} ngày), {len(yt)} lượt muốn đến."))
