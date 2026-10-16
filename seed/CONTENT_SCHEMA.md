# Schema nội dung (JSON, UTF-8)

## content_ranked.json / content_kiemke.json : mảng object
{
  "ma": "VD01",                       // khớp di_tich_chuan.json
  "ten": {"vi": "...", "en": "...", "zh": "..."},        // tên hiển thị gọn (VD01 rút gọn: "Quần thể Thương cảng Vân Đồn")
  "ten_khac": "tên gọi khác, cách nhau dấu phẩy (tiếng Việt)",
  "tom_tat": {"vi": "1–3 câu ≤ 400 ký tự", "en": "...", "zh": "..."},
  "noi_dung": {"vi": "<h3>Lịch sử</h3><p>...</p>...", "en": "...", "zh": "..."},
      // HTML chỉ dùng thẻ: h3, p, ul, li, strong, em, blockquote. Mục gợi ý: Lịch sử; Giá trị; Kiến trúc, cảnh quan; Truyền thuyết, tín ngưỡng; Lễ hội.
  "thong_tin_tham_quan": {"vi": "<p>...</p>", "en": "...", "zh": "..."},   // cách đi (tàu từ cảng Ao Tiên nếu trên đảo), lưu ý trang phục... KHÔNG ghi giá vé tàu/ giờ tàu cụ thể
  "gio_mo_cua": {"vi": "", "en": "", "zh": ""},          // để "" nếu không có nguồn
  "hien_trang": "tot|tu_bo|phe_tich|khac",
  "hien_trang_mo_ta": {"vi": "...", "en": "...", "zh": "..."},
  "tham_quan_duoc": true,
  "so_quyet_dinh": "Số 1225/QĐ-TTg ngày 24/10/2023", "co_quan_qd": "Thủ tướng Chính phủ", "nam_xep_hang": 2023,
  "dien_tich": "…",                                    // từ PDF danh mục nếu có
  "noi_bat": true,
  "diem_ten": {"<tên điểm như trong di_tich_chuan.json diem[].ten>": {"en": "...", "zh": "..."}},
  "nguon": [{"ten": "Báo Quảng Ninh – <tiêu đề>", "url": "https://...", "ngay": "13/09/2022"}],
  "chua_xac_minh": ["ghi chú các điểm thông tin còn mâu thuẫn/ chưa xác minh"]
}

## content_misc.json : object
{
 "tuyen": [ {"ten": {vi,en,zh}, "mo_ta": {vi,en,zh html}, "thoi_luong": {vi,en,zh}, "phuong_tien": {vi,en,zh}, "diem": [{"ma":"VD01","ghi_chu":{vi,en,zh}}] } ],
 "le_hoi": [ {"ten":{...}, "mo_ta":{... html}, "thoi_gian_am_lich":{...}, "thoi_gian_duong_lich":{...}, "thang_sap_xep": 1-12, "dia_diem":{...}, "cong_nhan":{...}, "di_tich":["VD02"], "nguon":"tên + url"} ],
 "thong_tin": [ {"nhom":"di_lai|luu_tru|y_te|lien_he|luu_y", "tieu_de":{...}, "noi_dung":{... html}, "lien_ket":"https://...", "nguon":"tên + url + ngày", "ngay_cap_nhat":"2026-10-16"} ],
 "trang_tinh": [ {"slug":"gioi-thieu","tieu_de":{...},"noi_dung":{... html}}, {"slug":"chinh-sach-du-lieu", ...} ],
 "khu_vuc": {"Thắng Lợi": {"en":"Thang Loi","zh":"..."}, ...},
 "loai_hinh": {"Lịch sử": {"en":"Historical","zh":"历史"}, ...}
}
