# Ghi chú phát triển (nội bộ)

Dự án: Website giới thiệu, quảng bá di tích Đặc khu Vân Đồn – Django 5.2, Python 3.13, PostgreSQL 16.
TR đã duyệt: /home/claude/vandon/tr/TR_Website_Di_tich_Van_Don_v1.0.docx (đọc bằng `pandoc -t plain`).

## Chạy local
```
cd /home/claude/vandon/app
set -a; . ./.env.dev; set +a          # DATABASE_URL postgres local, DEBUG=1, ALLOWED_HOSTS có testserver
python3 manage.py runserver 0.0.0.0:8000   # đã chạy sẵn ở cổng 8000 (autoreload)
python3 manage.py load_vandon [--update]   # nạp 44 di tích + nội dung
python3 manage.py test
```
Khu quản trị: `/quan-tri-vd/` (settings.ADMIN_URL). Superuser bắt buộc OTP (AdminOTPMiddleware) – trong test đặt
`session["otp_ok"]=True`, hoặc chạy với env `OTP_REQUIRED_FOR_SUPERUSER=0` khi phát triển.

## Cấu trúc
- `core/`: SiteConfig (singleton, `SiteConfig.get()`), AdminProfile (OTP, khóa tạm), AuditLog (signals tự ghi), HelpArticle,
  utils (strip_accents, vn_slugify, parse_coordinates(DMS|decimal) -> (lat,lng,note), in_van_don, haversine_km, clean_html).
- `heritage/`: KhuVuc, LoaiHinh, DiTich, DiemDiTich, HinhAnh (signal tự sinh WebP: bien_the), Video, NguonThamKhao,
  TuyenThamQuan + DiemTuyen, LeHoi, ThongTinHuuIch, TinTuc, TrangTinh. Đa ngôn ngữ bằng django-modeltranslation:
  mỗi trường dịch có `<field>_vi`, `<field>_en`, `<field>_zh_hans` (xem heritage/translation.py).
  Quyền tùy biến: `heritage.publish_ditich`. Trạng thái: TrangThai (draft/review/published/hidden).
  `DiTich.missing_for_publish()` trả danh sách điều kiện xuất bản còn thiếu.
- `interactions/`: DanhGia, GopY (+AnhGopY, LichSuXuLy), YeuThich, LuotXem, TuCam.
- `dashboard/`: thống kê, kiểm duyệt nhanh, xuất Excel/CSV (URL names dashboard:index, dashboard:moderation, ...).
- Giao diện công khai: templates/base.html, templates/public/*, static/css/site.css, static/js/{site,map,chart}.js.
- Nhóm quyền (tạo bởi load_vandon): "Biên tập viên", "Duyệt nội dung", "Kiểm duyệt tương tác".

## Bảng màu (TR 7.1)
xanh ngọc #0E6B6B, xanh ngọc đậm #0A4A4E, xanh ngọc nhạt #E3EFEC, đỏ son #A3302A, vàng đồng #B8893A (chỉ trang trí),
vàng đồng chữ #84601F, nền giấy dó #F6F0E4, giấy dó đậm #EAE0CC, mực #2B2620, xám đá #6F675B.
Font: "Noto Serif" (tiêu đề), "Be Vietnam Pro" (nội dung) – đã self-host ở static/fonts/fonts.css.

## Quy ước
- Giao diện quản trị: tiếng Việt, thân thiện người không chuyên CNTT; mọi trường có help_text.
- Không dùng CDN cho JS/CSS quản trị; vendor vào static/vendor/.
- CSP ở core/middleware.py (SecurityHeadersMiddleware) – nếu cần thêm nguồn, ghi chú cho người tích hợp.
