from modeltranslation.translator import TranslationOptions, register

from .models import (DiemDiTich, DiTich, DiemTuyen, HinhAnh, KhuVuc, LeHoi, LoaiHinh, ThongTinHuuIch,
                     TinTuc, TrangTinh, TuyenThamQuan, Video)


@register(DiTich)
class DiTichTR(TranslationOptions):
    fields = ("ten", "dia_chi_moi", "tom_tat", "noi_dung", "thong_tin_tham_quan", "gio_mo_cua", "phi_tham_quan",
              "hien_trang_mo_ta", "seo_title", "seo_description")


@register(DiemDiTich)
class DiemTR(TranslationOptions):
    fields = ("ten", "mo_ta")


@register(KhuVuc)
class KhuVucTR(TranslationOptions):
    fields = ("ten", "dao")


@register(LoaiHinh)
class LoaiHinhTR(TranslationOptions):
    fields = ("ten",)


@register(HinhAnh)
class HinhAnhTR(TranslationOptions):
    fields = ("chu_thich",)


@register(Video)
class VideoTR(TranslationOptions):
    fields = ("tieu_de",)


@register(TuyenThamQuan)
class TuyenTR(TranslationOptions):
    fields = ("ten", "mo_ta", "thoi_luong", "phuong_tien")


@register(DiemTuyen)
class DiemTuyenTR(TranslationOptions):
    fields = ("ghi_chu",)


@register(LeHoi)
class LeHoiTR(TranslationOptions):
    fields = ("ten", "mo_ta", "thoi_gian_am_lich", "thoi_gian_duong_lich", "dia_diem", "cong_nhan")


@register(ThongTinHuuIch)
class TTHITR(TranslationOptions):
    fields = ("tieu_de", "noi_dung")


@register(TinTuc)
class TinTucTR(TranslationOptions):
    fields = ("tieu_de", "tom_tat", "noi_dung")


@register(TrangTinh)
class TrangTinhTR(TranslationOptions):
    fields = ("tieu_de", "noi_dung")
