"""Mô hình dữ liệu di tích (TR mục 4)."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.utils import clean_html_fields, strip_accents, vn_slugify


class PublishQuerySet(models.QuerySet):
    def published(self):
        return self.filter(trang_thai=TrangThai.PUBLISHED)


class TrangThai(models.TextChoices):
    DRAFT = "draft", "Nháp"
    REVIEW = "review", "Chờ duyệt"
    PUBLISHED = "published", "Đã xuất bản"
    HIDDEN = "hidden", "Ẩn"


class CapXepHang(models.TextChoices):
    QGDB = "qgdb", _("Quốc gia đặc biệt")
    QG = "qg", _("Quốc gia")
    TINH = "tinh", _("Cấp tỉnh")
    KIEMKE = "kiemke", _("Kiểm kê")


CAP_ORDER = {"qgdb": 0, "qg": 1, "tinh": 2, "kiemke": 3}


class HienTrang(models.TextChoices):
    TOT = "tot", _("Tốt")
    TU_BO = "tu_bo", _("Đã tu bổ, tôn tạo")
    PHE_TICH = "phe_tich", _("Phế tích")
    KHAC = "khac", _("Khác")


class KhuVuc(models.Model):
    ten = models.CharField("Tên khu vực/đảo", max_length=100)
    slug = models.SlugField(unique=True)
    la_dao = models.BooleanField("Thuộc đảo (cần đi tàu)", default=False,
                                 help_text="Đánh dấu nếu từ trung tâm Cái Rồng phải đi tàu mới tới.")
    dao = models.CharField("Tên đảo", max_length=100, blank=True,
                           help_text="Các khu vực cùng đảo ghi cùng tên (ví dụ Quan Lạn và Minh Châu cùng đảo Quan Lạn).")
    thu_tu = models.PositiveIntegerField("Thứ tự", default=0)

    class Meta:
        verbose_name = "Khu vực / đảo"
        verbose_name_plural = "Danh mục: Khu vực / đảo"
        ordering = ["thu_tu", "ten"]

    def __str__(self):
        return self.ten


class LoaiHinh(models.Model):
    ten = models.CharField("Loại hình", max_length=100)
    slug = models.SlugField(unique=True)
    thu_tu = models.PositiveIntegerField("Thứ tự", default=0)

    class Meta:
        verbose_name = "Loại hình di tích"
        verbose_name_plural = "Danh mục: Loại hình di tích"
        ordering = ["thu_tu"]

    def __str__(self):
        return self.ten


class DiTich(models.Model):
    ma = models.CharField("Mã di tích", max_length=20, unique=True, help_text="Ví dụ VD01. Không trùng.")
    ten = models.CharField("Tên di tích", max_length=300)
    ten_khac = models.CharField("Tên gọi khác", max_length=300, blank=True,
                                help_text="Tên dân gian, tên chữ… dùng cho tìm kiếm. Ví dụ: đền Cậu.")
    slug = models.SlugField("Đường dẫn", max_length=200, unique=True, blank=True,
                            help_text="Tự sinh từ tên nếu để trống.")
    cap_xep_hang = models.CharField("Cấp xếp hạng", max_length=10, choices=CapXepHang.choices)
    loai_hinh = models.ManyToManyField(LoaiHinh, verbose_name="Loại hình", related_name="di_tich")
    khu_vuc = models.ForeignKey(KhuVuc, verbose_name="Khu vực / đảo", on_delete=models.PROTECT, related_name="di_tich")
    khu_vuc_phu = models.ManyToManyField(KhuVuc, verbose_name="Khu vực khác", blank=True, related_name="di_tich_phu",
                                         help_text="Chỉ dùng khi di tích trải trên nhiều khu vực (ví dụ Thương cảng).")
    dia_chi_cu = models.CharField("Địa điểm trước 01/7/2025", max_length=300, blank=True)
    dia_chi_moi = models.CharField("Địa điểm từ 01/7/2025", max_length=300)
    so_quyet_dinh = models.CharField("Số quyết định xếp hạng", max_length=200, blank=True)
    co_quan_qd = models.CharField("Cơ quan ra quyết định", max_length=200, blank=True)
    nam_xep_hang = models.PositiveIntegerField("Năm xếp hạng / kiểm kê", null=True, blank=True)
    dien_tich = models.CharField("Diện tích", max_length=300, blank=True)
    hien_trang = models.CharField("Hiện trạng", max_length=10, choices=HienTrang.choices, default=HienTrang.TOT)
    hien_trang_mo_ta = models.CharField("Mô tả hiện trạng", max_length=500, blank=True)
    tham_quan_duoc = models.BooleanField("Du khách tham quan được", default=True,
                                         help_text="Bỏ chọn với phế tích chỉ để tra cứu.")
    tom_tat = models.TextField("Tóm tắt", max_length=600, help_text="1–3 câu, hiển thị ở thẻ danh sách và chia sẻ mạng xã hội.")
    noi_dung = models.TextField("Bài giới thiệu", blank=True,
                                help_text="Chia mục bằng Tiêu đề: Lịch sử; Giá trị; Kiến trúc, cảnh quan; Truyền thuyết, tín ngưỡng; Lễ hội.")
    thong_tin_tham_quan = models.TextField("Hướng dẫn tham quan", blank=True,
                                           help_text="Cách đi, thời điểm nên đến, trang phục, lưu ý.")
    gio_mo_cua = models.CharField("Giờ mở cửa", max_length=200, blank=True)
    phi_tham_quan = models.CharField("Phí tham quan", max_length=200, default="Miễn phí")
    lien_he = models.CharField("Đơn vị quản lý / liên hệ", max_length=300, blank=True)
    noi_bat = models.BooleanField("Nổi bật (hiện ở trang chủ)", default=False)
    thu_tu = models.PositiveIntegerField("Thứ tự ưu tiên", default=100)
    anh_dai_dien = models.ForeignKey("HinhAnh", verbose_name="Ảnh đại diện", null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="+")
    seo_title = models.CharField("Tiêu đề SEO", max_length=200, blank=True)
    seo_description = models.CharField("Mô tả SEO", max_length=300, blank=True)
    trang_thai = models.CharField("Trạng thái", max_length=12, choices=TrangThai.choices, default=TrangThai.DRAFT)
    search_text = models.TextField(editable=False, blank=True)
    luot_xem = models.PositiveIntegerField("Lượt xem", default=0, editable=False)
    nguoi_tao = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="+", editable=False)
    nguoi_sua = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="+", editable=False)
    ngay_tao = models.DateTimeField(auto_now_add=True)
    ngay_sua = models.DateTimeField(auto_now=True)

    objects = PublishQuerySet.as_manager()

    class Meta:
        verbose_name = "Di tích"
        verbose_name_plural = "Di tích"
        ordering = ["thu_tu", "ma"]
        permissions = [("publish_ditich", "Được xuất bản / ẩn di tích")]

    def __str__(self):
        return f"{self.ma} – {self.ten}"

    # ---- tiện ích ----
    def get_absolute_url(self):
        return reverse("heritage:detail", kwargs={"slug": self.slug})

    @property
    def cap_order(self):
        return CAP_ORDER.get(self.cap_xep_hang, 9)

    def missing_for_publish(self):
        """Danh sách điều kiện xuất bản còn thiếu (TR FR-A09)."""
        miss = []
        if not (getattr(self, "ten_vi", None) or self.ten):
            miss.append("tên tiếng Việt")
        if not (getattr(self, "tom_tat_vi", None) or self.tom_tat):
            miss.append("tóm tắt tiếng Việt")
        if not self.anh_dai_dien_id:
            miss.append("ảnh đại diện")
        if not self.cap_xep_hang:
            miss.append("cấp xếp hạng")
        if not self.khu_vuc_id:
            miss.append("khu vực")
        return miss

    def completeness(self):
        pts = list(self.diem.all())
        return {
            "anh": self.hinh_anh.count(),
            "toa_do": sum(1 for p in pts if p.vi_do is not None),
            "diem": len(pts),
            "en": bool(getattr(self, "tom_tat_en", "")),
            "zh": bool(getattr(self, "tom_tat_zh_hans", "")),
            "noi_dung": len(strip_accents(getattr(self, "noi_dung_vi", "") or "")),
        }

    @property
    def diem_chinh(self):
        pts = [p for p in self.diem.all() if p.vi_do is not None]
        for p in pts:
            if p.diem_chinh:
                return p
        return pts[0] if pts else None

    def build_search_text(self):
        parts = [self.ma, self.ten, self.ten_khac, self.dia_chi_moi, self.dia_chi_cu, self.tom_tat]
        for lang in ("vi", "en", "zh_hans"):
            parts += [getattr(self, f"ten_{lang}", ""), getattr(self, f"tom_tat_{lang}", "")]
        if self.khu_vuc_id:
            parts.append(self.khu_vuc.ten)
        txt = " ".join(p for p in parts if p)
        return f"{txt.lower()} {strip_accents(txt)}"

    def clean(self):
        if self.trang_thai == TrangThai.PUBLISHED and self.pk:
            miss = self.missing_for_publish()
            if miss:
                raise ValidationError(
                    {"trang_thai": "Chưa thể xuất bản. Còn thiếu: " + ", ".join(miss) + ". Có thể lưu ở trạng thái Nháp hoặc Chờ duyệt."}
                )

    def save(self, *args, **kwargs):
        if not self.slug:
            base = vn_slugify(getattr(self, "ten_vi", None) or self.ten)
            slug, i = base, 2
            while DiTich.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        clean_html_fields(self, ["noi_dung", "thong_tin_tham_quan"])
        if self.khu_vuc_id:
            self.search_text = self.build_search_text()
        super().save(*args, **kwargs)


class DoTinCay(models.TextChoices):
    THUC_DIA = "thuc_dia", "Đã xác minh thực địa"
    DANH_MUC = "danh_muc", "Theo danh mục"
    TUONG_DOI = "tuong_doi", "Vị trí tương đối"
    CHUA = "chua", "Chưa xác minh"


class DiemDiTich(models.Model):
    di_tich = models.ForeignKey(DiTich, on_delete=models.CASCADE, related_name="diem", verbose_name="Di tích")
    ten = models.CharField("Tên điểm", max_length=300)
    vi_do = models.DecimalField("Vĩ độ", max_digits=9, decimal_places=6, null=True, blank=True)
    kinh_do = models.DecimalField("Kinh độ", max_digits=9, decimal_places=6, null=True, blank=True)
    toa_do_goc = models.CharField("Tọa độ gốc (như nhập)", max_length=120, blank=True)
    do_tin_cay = models.CharField("Độ tin cậy", max_length=12, choices=DoTinCay.choices, default=DoTinCay.CHUA)
    mo_ta = models.TextField("Mô tả ngắn", blank=True)
    diem_chinh = models.BooleanField("Điểm chính", default=False,
                                     help_text="Điểm dùng làm tâm bản đồ và nút Chỉ đường.")
    thu_tu = models.PositiveIntegerField("Thứ tự", default=0)

    class Meta:
        verbose_name = "Điểm di tích"
        verbose_name_plural = "Điểm di tích"
        ordering = ["thu_tu", "id"]

    def __str__(self):
        return self.ten

    @property
    def has_coord(self):
        return self.vi_do is not None and self.kinh_do is not None

    @property
    def lat(self):
        return float(self.vi_do) if self.vi_do is not None else None

    @property
    def lng(self):
        return float(self.kinh_do) if self.kinh_do is not None else None

    def directions_url(self):
        if not self.has_coord:
            return ""
        return f"https://www.google.com/maps/dir/?api=1&destination={self.lat},{self.lng}"


def upload_to_anh(instance, filename):
    d = timezone.now()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    return f"anh/{d:%Y/%m}/{vn_slugify(filename.rsplit('.', 1)[0])[:60]}-{d:%H%M%S%f}.{ext}"


class HinhAnh(models.Model):
    di_tich = models.ForeignKey(DiTich, on_delete=models.CASCADE, related_name="hinh_anh", null=True, blank=True,
                                verbose_name="Di tích")
    diem = models.ForeignKey(DiemDiTich, on_delete=models.SET_NULL, related_name="hinh_anh", null=True, blank=True,
                             verbose_name="Điểm di tích")
    tep = models.ImageField("Tệp ảnh", upload_to=upload_to_anh)
    chu_thich = models.CharField("Chú thích", max_length=300, blank=True)
    tac_gia = models.CharField("Tác giả", max_length=200, blank=True)
    nguon = models.CharField("Nguồn / bản quyền", max_length=300,
                             help_text="Bắt buộc. Ví dụ: Ảnh: Phòng VHXH Vân Đồn; hoặc Báo Quảng Ninh (đã xin phép).")
    ngay_chup = models.DateField("Ngày chụp", null=True, blank=True)
    thu_tu = models.PositiveIntegerField("Thứ tự", default=0)
    rong = models.PositiveIntegerField(default=0, editable=False)
    cao = models.PositiveIntegerField(default=0, editable=False)
    bien_the = models.JSONField(default=dict, blank=True, editable=False)  # {"480": "path.webp", ...}
    la_minh_hoa = models.BooleanField("Ảnh minh họa tạm", default=False,
                                      help_text="Ảnh giữ chỗ do hệ thống tạo, cần thay bằng ảnh chính thức.")
    ngay_tao = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ảnh"
        verbose_name_plural = "Thư viện ảnh"
        ordering = ["thu_tu", "id"]

    def __str__(self):
        return self.chu_thich or self.tep.name.rsplit("/", 1)[-1]

    def url(self, size=960):
        from django.conf import settings as s
        if self.bien_the:
            sizes = sorted(int(k) for k in self.bien_the)
            pick = next((k for k in sizes if k >= size), sizes[-1])
            return s.MEDIA_URL + self.bien_the[str(pick)]
        return self.tep.url

    def srcset(self):
        from django.conf import settings as s
        if not self.bien_the:
            return ""
        return ", ".join(f"{s.MEDIA_URL}{p} {k}w" for k, p in sorted(self.bien_the.items(), key=lambda x: int(x[0])))


class Video(models.Model):
    di_tich = models.ForeignKey(DiTich, on_delete=models.CASCADE, related_name="videos", verbose_name="Di tích")
    tieu_de = models.CharField("Tiêu đề", max_length=300)
    youtube_url = models.URLField("Liên kết YouTube", blank=True)
    tep = models.FileField("Tệp MP4", upload_to="video/%Y/%m", blank=True)
    nguon = models.CharField("Nguồn / bản quyền", max_length=300)
    thu_tu = models.PositiveIntegerField("Thứ tự", default=0)

    class Meta:
        verbose_name = "Video"
        verbose_name_plural = "Video"
        ordering = ["thu_tu", "id"]

    def __str__(self):
        return self.tieu_de

    @property
    def youtube_id(self):
        import re
        m = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})", self.youtube_url or "")
        return m.group(1) if m else ""

    def clean(self):
        if not self.youtube_url and not self.tep:
            raise ValidationError("Cần dán liên kết YouTube hoặc tải tệp MP4.")
        if self.youtube_url and not self.youtube_id:
            raise ValidationError({"youtube_url": "Liên kết YouTube không hợp lệ."})


class NguonThamKhao(models.Model):
    di_tich = models.ForeignKey(DiTich, on_delete=models.CASCADE, related_name="nguon", verbose_name="Di tích")
    ten = models.CharField("Tên nguồn / tiêu đề", max_length=400)
    url = models.URLField("Đường dẫn", max_length=500, blank=True)
    ngay = models.CharField("Ngày đăng / truy cập", max_length=50, blank=True)
    thu_tu = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Nguồn tham khảo"
        verbose_name_plural = "Nguồn tham khảo"
        ordering = ["thu_tu", "id"]

    def __str__(self):
        return self.ten


class TuyenThamQuan(models.Model):
    ten = models.CharField("Tên tuyến", max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    mo_ta = models.TextField("Mô tả")
    thoi_luong = models.CharField("Thời lượng gợi ý", max_length=100, blank=True)
    phuong_tien = models.CharField("Phương tiện", max_length=200, blank=True)
    anh_bia = models.ForeignKey(HinhAnh, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                                verbose_name="Ảnh bìa")
    thu_tu = models.PositiveIntegerField("Thứ tự", default=0)
    trang_thai = models.CharField("Trạng thái", max_length=12, choices=TrangThai.choices, default=TrangThai.PUBLISHED)

    objects = PublishQuerySet.as_manager()

    class Meta:
        verbose_name = "Tuyến tham quan"
        verbose_name_plural = "Tuyến tham quan"
        ordering = ["thu_tu"]

    def __str__(self):
        return self.ten

    def save(self, *a, **k):
        if not self.slug:
            self.slug = vn_slugify(getattr(self, "ten_vi", None) or self.ten)
        clean_html_fields(self, ["mo_ta"])
        super().save(*a, **k)

    def get_absolute_url(self):
        return reverse("heritage:route", kwargs={"slug": self.slug})


class DiemTuyen(models.Model):
    tuyen = models.ForeignKey(TuyenThamQuan, on_delete=models.CASCADE, related_name="diem_tuyen")
    di_tich = models.ForeignKey(DiTich, on_delete=models.CASCADE, verbose_name="Di tích")
    ghi_chu = models.CharField("Ghi chú", max_length=300, blank=True)
    thu_tu = models.PositiveIntegerField("Thứ tự", default=0)

    class Meta:
        verbose_name = "Điểm dừng"
        verbose_name_plural = "Các điểm dừng (theo thứ tự)"
        ordering = ["thu_tu"]


class LeHoi(models.Model):
    ten = models.CharField("Tên lễ hội / sự kiện", max_length=300)
    slug = models.SlugField(unique=True, blank=True)
    mo_ta = models.TextField("Mô tả")
    thoi_gian_am_lich = models.CharField("Thời gian (âm lịch)", max_length=200, blank=True)
    thoi_gian_duong_lich = models.CharField("Thời gian (dương lịch)", max_length=200, blank=True)
    thang_sap_xep = models.PositiveSmallIntegerField("Tháng (để sắp xếp, 1–12)", default=1)
    dia_diem = models.CharField("Địa điểm", max_length=300, blank=True)
    di_tich = models.ManyToManyField(DiTich, blank=True, verbose_name="Di tích liên quan", related_name="le_hoi")
    anh = models.ForeignKey(HinhAnh, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="Ảnh")
    cong_nhan = models.CharField("Công nhận", max_length=300, blank=True,
                                 help_text="Ví dụ: Di sản văn hóa phi vật thể quốc gia.")
    nguon = models.CharField("Nguồn", max_length=400, blank=True)
    trang_thai = models.CharField("Trạng thái", max_length=12, choices=TrangThai.choices, default=TrangThai.PUBLISHED)

    objects = PublishQuerySet.as_manager()

    class Meta:
        verbose_name = "Lễ hội, sự kiện"
        verbose_name_plural = "Lễ hội, sự kiện"
        ordering = ["thang_sap_xep", "ten"]

    def __str__(self):
        return self.ten

    def save(self, *a, **k):
        if not self.slug:
            self.slug = vn_slugify(getattr(self, "ten_vi", None) or self.ten)
        clean_html_fields(self, ["mo_ta"])
        super().save(*a, **k)


class ThongTinHuuIch(models.Model):
    class Nhom(models.TextChoices):
        DI_LAI = "di_lai", _("Đi lại")
        LUU_TRU = "luu_tru", _("Lưu trú")
        Y_TE = "y_te", _("Y tế, khẩn cấp")
        LIEN_HE = "lien_he", _("Liên hệ")
        LUU_Y = "luu_y", _("Lưu ý khi tham quan")

    nhom = models.CharField("Nhóm", max_length=12, choices=Nhom.choices)
    tieu_de = models.CharField("Tiêu đề", max_length=300)
    noi_dung = models.TextField("Nội dung")
    lien_ket = models.URLField("Liên kết ngoài", blank=True)
    nguon = models.CharField("Nguồn thông tin", max_length=400, blank=True)
    ngay_cap_nhat = models.DateField("Ngày cập nhật", default=timezone.localdate,
                                     help_text="Hiển thị công khai để du khách biết độ mới của thông tin.")
    thu_tu = models.PositiveIntegerField("Thứ tự", default=0)
    trang_thai = models.CharField("Trạng thái", max_length=12, choices=TrangThai.choices, default=TrangThai.PUBLISHED)

    objects = PublishQuerySet.as_manager()

    class Meta:
        verbose_name = "Thông tin hữu ích"
        verbose_name_plural = "Thông tin hữu ích"
        ordering = ["nhom", "thu_tu"]

    def __str__(self):
        return self.tieu_de

    def save(self, *a, **k):
        clean_html_fields(self, ["noi_dung"])
        super().save(*a, **k)


class TinTuc(models.Model):
    tieu_de = models.CharField("Tiêu đề", max_length=300)
    slug = models.SlugField(unique=True, blank=True, max_length=200)
    tom_tat = models.TextField("Tóm tắt", blank=True)
    noi_dung = models.TextField("Nội dung")
    anh = models.ForeignKey(HinhAnh, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="Ảnh")
    ngay_dang = models.DateTimeField("Ngày đăng", default=timezone.now)
    trang_thai = models.CharField("Trạng thái", max_length=12, choices=TrangThai.choices, default=TrangThai.DRAFT)

    objects = PublishQuerySet.as_manager()

    class Meta:
        verbose_name = "Tin tức"
        verbose_name_plural = "Tin tức"
        ordering = ["-ngay_dang"]

    def __str__(self):
        return self.tieu_de

    def save(self, *a, **k):
        if not self.slug:
            self.slug = vn_slugify(getattr(self, "tieu_de_vi", None) or self.tieu_de)
        clean_html_fields(self, ["noi_dung"])
        super().save(*a, **k)

    def get_absolute_url(self):
        return reverse("heritage:news_detail", kwargs={"slug": self.slug})


class TrangTinh(models.Model):
    slug = models.SlugField(unique=True)
    tieu_de = models.CharField("Tiêu đề", max_length=300)
    noi_dung = models.TextField("Nội dung")

    class Meta:
        verbose_name = "Trang tĩnh"
        verbose_name_plural = "Trang tĩnh (Giới thiệu, Chính sách…)"

    def __str__(self):
        return self.tieu_de

    def save(self, *a, **k):
        clean_html_fields(self, ["noi_dung"])
        super().save(*a, **k)
