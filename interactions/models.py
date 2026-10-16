"""Tương tác người dùng (TR mục 5.2) và đo lượt xem (TR 5.5)."""
from django.conf import settings
from django.db import models
from django.utils import timezone

from heritage.models import DiTich


class TrangThaiDuyet(models.TextChoices):
    PENDING = "pending", "Chờ duyệt"
    APPROVED = "approved", "Đã duyệt"
    HIDDEN = "hidden", "Ẩn"
    SPAM = "spam", "Spam"


class DanhGia(models.Model):
    di_tich = models.ForeignKey(DiTich, on_delete=models.CASCADE, related_name="danh_gia", verbose_name="Di tích")
    so_sao = models.PositiveSmallIntegerField("Số sao", choices=[(i, f"{i} sao") for i in range(1, 6)])
    noi_dung = models.TextField("Nhận xét", max_length=1000)
    ten_hien_thi = models.CharField("Tên hiển thị", max_length=80)
    email = models.EmailField("Email", blank=True)
    dien_thoai = models.CharField("Điện thoại", max_length=20, blank=True)
    ngon_ngu = models.CharField("Ngôn ngữ", max_length=10, default="vi")
    dong_y = models.BooleanField("Đồng ý xử lý dữ liệu", default=False)
    trang_thai = models.CharField("Trạng thái", max_length=10, choices=TrangThaiDuyet.choices,
                                  default=TrangThaiDuyet.PENDING, db_index=True)
    nghi_spam = models.BooleanField("Nghi spam", default=False)
    ly_do_nghi = models.CharField("Lý do nghi", max_length=200, blank=True)
    phan_hoi = models.TextField("Phản hồi của Ban quản trị", blank=True)
    nguoi_duyet = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+", verbose_name="Người duyệt")
    ngay_duyet = models.DateTimeField("Ngày duyệt", null=True, blank=True)
    ip_hash = models.CharField(max_length=64, blank=True, editable=False)
    ngay_tao = models.DateTimeField("Thời gian gửi", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "Đánh giá, nhận xét"
        verbose_name_plural = "Đánh giá, nhận xét"
        ordering = ["-ngay_tao"]

    def __str__(self):
        return f"{self.so_sao}★ {self.ten_hien_thi} – {self.di_tich.ten}"


class GopY(models.Model):
    class Loai(models.TextChoices):
        DICH_VU = "dich_vu", "Góp ý dịch vụ"
        MONG_MUON = "mong_muon", "Mong muốn, đề xuất"
        XUONG_CAP = "xuong_cap", "Báo di tích xuống cấp"
        HOI_DAP = "hoi_dap", "Hỏi đáp"
        KHAC = "khac", "Khác"

    class XuLy(models.TextChoices):
        MOI = "moi", "Mới"
        DANG = "dang", "Đang xử lý"
        XONG = "xong", "Đã xử lý"
        DONG = "dong", "Đóng"

    ma_tra_cuu = models.CharField("Mã tra cứu", max_length=20, unique=True, editable=False)
    loai = models.CharField("Loại góp ý", max_length=12, choices=Loai.choices)
    di_tich = models.ForeignKey(DiTich, on_delete=models.SET_NULL, null=True, blank=True, related_name="gop_y",
                                verbose_name="Di tích liên quan")
    noi_dung = models.TextField("Nội dung", max_length=3000)
    ho_ten = models.CharField("Họ tên", max_length=100, blank=True)
    email = models.EmailField("Email", blank=True)
    dien_thoai = models.CharField("Điện thoại", max_length=20, blank=True)
    ngon_ngu = models.CharField("Ngôn ngữ", max_length=10, default="vi")
    dong_y = models.BooleanField("Đồng ý xử lý dữ liệu", default=False)
    trang_thai = models.CharField("Trạng thái xử lý", max_length=6, choices=XuLy.choices, default=XuLy.MOI, db_index=True)
    nghi_spam = models.BooleanField("Nghi spam", default=False)
    nguoi_xu_ly = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+", verbose_name="Người xử lý")
    ghi_chu_noi_bo = models.TextField("Ghi chú nội bộ", blank=True)
    phan_hoi = models.TextField("Phản hồi cho người gửi", blank=True)
    cong_khai = models.BooleanField("Công khai trong mục Hỏi đáp", default=False)
    ngay_xu_ly = models.DateTimeField("Ngày hoàn thành", null=True, blank=True)
    ip_hash = models.CharField(max_length=64, blank=True, editable=False)
    ngay_tao = models.DateTimeField("Thời gian gửi", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "Góp ý, mong muốn"
        verbose_name_plural = "Góp ý, mong muốn"
        ordering = ["-ngay_tao"]

    def __str__(self):
        return f"{self.ma_tra_cuu} – {self.get_loai_display()}"

    def save(self, *a, **k):
        if not self.ma_tra_cuu:
            year = timezone.localdate().year
            last = GopY.objects.filter(ma_tra_cuu__startswith=f"GY-{year}-").order_by("-ma_tra_cuu").first()
            n = int(last.ma_tra_cuu.rsplit("-", 1)[1]) + 1 if last else 1
            self.ma_tra_cuu = f"GY-{year}-{n:05d}"
        if self.trang_thai == self.XuLy.XONG and not self.ngay_xu_ly:
            self.ngay_xu_ly = timezone.now()
        super().save(*a, **k)


class AnhGopY(models.Model):
    gop_y = models.ForeignKey(GopY, on_delete=models.CASCADE, related_name="anh")
    tep = models.ImageField(upload_to="gop-y/%Y/%m")


class LichSuXuLy(models.Model):
    gop_y = models.ForeignKey(GopY, on_delete=models.CASCADE, related_name="lich_su")
    nguoi = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    noi_dung = models.CharField(max_length=500)
    thoi_gian = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-thoi_gian"]


class YeuThich(models.Model):
    """Nút "Muốn đến" – 1 lượt/trình duyệt/di tích (TR FR-I04)."""
    di_tich = models.ForeignKey(DiTich, on_delete=models.CASCADE, related_name="yeu_thich")
    ma_trinh_duyet = models.CharField(max_length=64)
    ngay_tao = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        unique_together = [("di_tich", "ma_trinh_duyet")]
        verbose_name = "Lượt muốn đến"
        verbose_name_plural = "Lượt muốn đến"


class LuotXem(models.Model):
    """Lượt xem tổng hợp theo ngày; không lưu IP, không cookie theo dõi."""
    ngay = models.DateField(db_index=True)
    duong_dan = models.CharField(max_length=300)
    di_tich = models.ForeignKey(DiTich, null=True, blank=True, on_delete=models.CASCADE, related_name="luot_xem_ngay")
    ngon_ngu = models.CharField(max_length=10)
    thiet_bi = models.CharField(max_length=10)  # mobile / tablet / desktop
    so_luot = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("ngay", "duong_dan", "ngon_ngu", "thiet_bi")]
        verbose_name = "Lượt xem"
        verbose_name_plural = "Lượt xem"


class TuCam(models.Model):
    tu = models.CharField("Từ / cụm từ cấm", max_length=100, unique=True)

    class Meta:
        verbose_name = "Từ ngữ cấm"
        verbose_name_plural = "Danh mục: Từ ngữ cấm"

    def __str__(self):
        return self.tu
