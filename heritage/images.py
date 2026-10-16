"""Xử lý ảnh tải lên: xoay theo EXIF, xóa GPS/EXIF, sinh các bản WebP (TR FR-A05, NFR-03)."""
import io
import os

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()  # cho phép ảnh HEIC từ iPhone
except Exception:  # pragma: no cover
    pass

SIZES = (480, 960, 1600, 2400)
MAX_ORIGINAL = 3200
MIN_RECOMMENDED = 1600


def process_image(hinh):
    """Chuẩn hóa ảnh gốc và sinh biến thể. Trả về danh sách cảnh báo (chuỗi)."""
    warnings = []
    f = hinh.tep
    f.open("rb")
    img = Image.open(f)
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    w, h = img.size
    if w < MIN_RECOMMENDED:
        warnings.append(f"Ảnh '{os.path.basename(f.name)}' rộng {w}px, nhỏ hơn mức khuyến nghị {MIN_RECOMMENDED}px.")
    # Ảnh gốc: thu về tối đa 3200px, lưu lại không kèm EXIF (xóa GPS)
    if max(w, h) > MAX_ORIGINAL:
        img.thumbnail((MAX_ORIGINAL, MAX_ORIGINAL), Image.LANCZOS)
    buf = io.BytesIO()
    base, _ = os.path.splitext(f.name)
    rgb = img.convert("RGB")
    rgb.save(buf, format="JPEG", quality=88, optimize=True, progressive=True)
    f.close()
    storage = f.storage
    old_name = f.name
    new_name = storage.save(base + ".jpg", ContentFile(buf.getvalue()))
    if new_name != old_name:
        try:
            storage.delete(old_name)
        except Exception:
            pass
    hinh.tep.name = new_name
    hinh.rong, hinh.cao = rgb.size
    # Biến thể WebP
    variants = {}
    for s in SIZES:
        if s > rgb.size[0] and s != SIZES[0]:
            continue
        v = rgb.copy()
        v.thumbnail((s, s * 2), Image.LANCZOS)
        b = io.BytesIO()
        v.save(b, format="WEBP", quality=80, method=5)
        vname = storage.save(f"{os.path.splitext(new_name)[0]}-{s}.webp", ContentFile(b.getvalue()))
        variants[str(s)] = vname
    for old in (hinh.bien_the or {}).values():
        try:
            storage.delete(old)
        except Exception:
            pass
    hinh.bien_the = variants
    return warnings


def delete_files(hinh):
    storage = hinh.tep.storage
    for p in list((hinh.bien_the or {}).values()) + [hinh.tep.name]:
        try:
            if p:
                storage.delete(p)
        except Exception:
            pass
