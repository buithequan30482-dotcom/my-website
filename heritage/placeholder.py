"""Tạo ảnh minh họa tạm (giữ chỗ) theo bảng màu dự án, cho tới khi có ảnh chính thức.

Ảnh tạo ra luôn có nhãn "Ảnh minh họa" và được đánh dấu la_minh_hoa=True để quản trị viên thay thế.
"""
import io
import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

TEAL = (14, 107, 107)
TEAL_D = (10, 74, 78)
SON = (163, 48, 42)
DONG = (184, 137, 58)
PAPER = (246, 240, 228)

FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def motif_for(name: str, loai: str) -> str:
    n = (name + " " + loai).lower()
    if "bãi tắm" in n:
        return "beach"
    if "hang" in n or "động" in n or "danh lam" in n or "dltc" in n:
        return "karst"
    if "bến" in n or "thương cảng" in n or "vụng" in n or "đường mòn" in n:
        return "boat"
    if any(k in n for k in ("đình", "đền", "miếu", "chùa", "nghè", "nhà thờ")):
        return "roof"
    if "khảo cổ" in n:
        return "pottery"
    return "karst"


def make_placeholder(title: str, motif: str, seed: int = 0, size=(2400, 1500)) -> bytes:
    rnd = random.Random(seed)
    W, H = size
    img = Image.new("RGB", size, PAPER)
    d = ImageDraw.Draw(img)
    horizon = int(H * 0.62)
    # Bầu trời: giấy dó -> xanh ngọc nhạt
    for y in range(horizon):
        d.line([(0, y), (W, y)], fill=_lerp((236, 228, 210), (205, 226, 222), y / horizon))
    # Mặt trời / trăng đồng
    cx, cy, r = int(W * (0.68 + rnd.random() * 0.15)), int(H * 0.28), int(H * 0.09)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(222, 190, 130))
    # Dãy núi đá vôi xa
    for layer, col in ((0, (150, 185, 180)), (1, (95, 150, 146))):
        pts = [(0, horizon)]
        x = 0
        while x < W:
            w = rnd.randint(120, 320)
            h = rnd.randint(int(H * 0.08), int(H * (0.22 if layer else 0.3)))
            pts += [(x + w * 0.2, horizon - h * 0.9), (x + w * 0.5, horizon - h), (x + w * 0.8, horizon - h * 0.85), (x + w, horizon)]
            x += w + rnd.randint(40, 260)
        pts.append((W, horizon))
        d.polygon(pts, fill=col)
    # Biển
    for y in range(horizon, H):
        d.line([(0, y), (W, y)], fill=_lerp(TEAL, TEAL_D, (y - horizon) / (H - horizon)))
    # Sóng đồng
    for i in range(9):
        yy = horizon + 30 + i * (H - horizon) // 9
        amp = 6 + i * 1.5
        pts = [(x, yy + math.sin(x / (60 + i * 8) + i) * amp) for x in range(0, W + 20, 20)]
        d.line(pts, fill=_lerp(DONG, TEAL, 0.35 + i * 0.05), width=2 + i // 3)
    # Họa tiết chính
    if motif == "roof":
        bx, by, bw = W * 0.18, horizon + 10, W * 0.42
        d.rectangle([bx + bw * 0.12, by - H * 0.16, bx + bw * 0.88, by], fill=(120, 50, 40))
        for k in range(5):
            x0 = bx + bw * (0.18 + k * 0.16)
            d.rectangle([x0, by - H * 0.13, x0 + bw * 0.07, by], fill=(95, 38, 32))
        roof = [(bx - bw * 0.04, by - H * 0.15), (bx + bw * 0.12, by - H * 0.27), (bx + bw * 0.88, by - H * 0.27),
                (bx + bw * 1.04, by - H * 0.15)]
        d.polygon(roof, fill=SON)
        d.line([(bx - bw * 0.07, by - H * 0.19), (bx - bw * 0.04, by - H * 0.15)], fill=SON, width=18)
        d.line([(bx + bw * 1.07, by - H * 0.19), (bx + bw * 1.04, by - H * 0.15)], fill=SON, width=18)
        d.line([(bx + bw * 0.12, by - H * 0.275), (bx + bw * 0.88, by - H * 0.275)], fill=DONG, width=10)
    elif motif == "boat":
        bx, by = W * 0.3, horizon + H * 0.12
        d.polygon([(bx - 260, by), (bx + 260, by), (bx + 200, by + 70), (bx - 200, by + 70)], fill=(70, 40, 30))
        d.line([(bx, by), (bx, by - 430)], fill=(70, 40, 30), width=12)
        for k in range(6):  # buồm cánh dơi có nan
            y0 = by - 420 + k * 62
            d.polygon([(bx + 8, y0), (bx + 250 - k * 6, y0 + 20), (bx + 240 - k * 6, y0 + 72), (bx + 8, y0 + 60)],
                      fill=SON if k % 2 == 0 else (184, 70, 58))
        d.line([(bx - 160, by - 300), (bx - 6, by - 330)], fill=(70, 40, 30), width=6)
    elif motif == "beach":
        d.polygon([(0, H), (0, horizon + 90), (W * 0.5, horizon + 220), (W * 0.9, H)], fill=(230, 214, 178))
        d.line([(0, horizon + 90), (W * 0.5, horizon + 220), (W * 0.9, H)], fill=(250, 248, 240), width=8)
        for k in range(4):  # rặng phi lao
            x0 = 80 + k * 140
            d.polygon([(x0, horizon + 90), (x0 + 50, horizon - 220 - k * 20), (x0 + 100, horizon + 90)], fill=(40, 90, 70))
    elif motif == "karst":
        for k, (x0, w, h) in enumerate(((W * 0.12, 360, 520), (W * 0.36, 260, 380), (W * 0.55, 420, 600))):
            pts = [(x0, horizon + 40), (x0 + w * 0.15, horizon - h * 0.7), (x0 + w * 0.4, horizon - h),
                   (x0 + w * 0.7, horizon - h * 0.8), (x0 + w, horizon + 40)]
            d.polygon(pts, fill=(48, 92, 86) if k != 1 else (60, 104, 98))
        d.ellipse([W * 0.6, horizon - 170, W * 0.6 + 170, horizon + 20], fill=(25, 40, 38))
    elif motif == "pottery":
        bx, by = W * 0.32, horizon + 120
        d.ellipse([bx - 220, by - 380, bx + 220, by + 40], fill=(232, 226, 210))
        d.rectangle([bx - 90, by - 470, bx + 90, by - 360], fill=(232, 226, 210))
        for k in range(3):
            d.arc([bx - 200, by - 330 + k * 90, bx + 200, by - 230 + k * 90], 0, 180, fill=(40, 80, 140), width=10)
    img = img.filter(ImageFilter.SMOOTH)
    d = ImageDraw.Draw(img)
    # Nhãn minh họa
    label = "ẢNH MINH HỌA – CHỜ ẢNH CHÍNH THỨC"
    f1 = _font(FONT_SANS, 34)
    tw = d.textlength(label, font=f1)
    d.rounded_rectangle([W - tw - 90, 40, W - 40, 110], radius=12, fill=(246, 240, 228))
    d.text((W - tw - 65, 56), label, font=f1, fill=SON)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=86)
    return buf.getvalue()
