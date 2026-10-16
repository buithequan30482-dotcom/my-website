"""Xuất bản xem trước TĨNH của cổng công khai (dùng cho GitHub Pages / trình diễn).

Bản tĩnh chỉ để xem giao diện và nội dung: gửi nhận xét, góp ý, tìm kiếm, lọc, "Muốn đến" không hoạt động.

    python manage.py export_static_preview --out ../preview --prefix /my-website/preview/
"""
import re
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.test import Client
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import translation

from heritage.models import DiTich, TrangTinh, TuyenThamQuan

ROOTS = ("vi", "en", "zh-hans", "static", "media", "qr", "api", "d", "i18n", "quan-tri-vd", "healthz", "sitemap.xml")
BANNER = {
    "vi": "Bản xem trước tĩnh trên GitHub Pages – gửi nhận xét, góp ý, tìm kiếm và lọc chỉ hoạt động khi chạy trên máy chủ.",
    "en": "Static preview on GitHub Pages – reviews, feedback, search and filters work only on the live server.",
    "zh-hans": "GitHub Pages 静态预览——评价、意见反馈、搜索和筛选仅在正式服务器上可用。",
}


class Command(BaseCommand):
    help = "Xuất bản xem trước tĩnh của website công khai"

    def add_arguments(self, p):
        p.add_argument("--out", required=True)
        p.add_argument("--prefix", default="/", help="Tiền tố URL nơi đặt bản tĩnh, ví dụ /my-website/preview/")

    def handle(self, out, prefix, **kw):
        out = Path(out).resolve()
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        prefix = "/" + prefix.strip("/") + "/" if prefix.strip("/") else "/"
        with override_settings(ALLOWED_HOSTS=["*"], DEBUG=True,
                               STORAGES={**settings.STORAGES, "staticfiles": {
                                   "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}):
            c = Client(HTTP_USER_AGENT="StaticExport/1.0 bot")
            pages = []
            for lang, _ in settings.LANGUAGES:
                with translation.override(lang):
                    pages += [reverse(n) for n in ("heritage:home", "heritage:list", "heritage:map", "heritage:routes",
                                                    "heritage:festivals", "heritage:useful", "heritage:news",
                                                    "interactions:feedback", "interactions:lookup")]
                    pages += [d.get_absolute_url() for d in DiTich.objects.published()]
                    pages += [r.get_absolute_url() for r in TuyenThamQuan.objects.published()]
                    pages += [reverse("heritage:page", kwargs={"slug": p.slug}) for p in TrangTinh.objects.all()]
            rx = re.compile(r'(?P<q>["\'(\s,])/(?P<r>' + "|".join(re.escape(r) for r in ROOTS) + r')(?=[/"\'?#)\s])')
            n = 0
            for url in pages:
                r = c.get(url)
                if r.status_code != 200:
                    self.stderr.write(f"Bỏ qua {url}: {r.status_code}")
                    continue
                html = r.content.decode()
                lang = url.strip("/").split("/")[0]
                html = rx.sub(lambda m: f"{m.group('q')}{prefix}{m.group('r')}", html)
                html = html.replace("<main id=\"main\">",
                                    f'<div style="background:#A3302A;color:#fff;padding:8px 16px;font-size:14px;text-align:center">'
                                    f'{BANNER.get(lang, BANNER["vi"])}</div><main id="main">', 1)
                dest = out / url.strip("/") / "index.html"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(html, "utf-8")
                n += 1
            # QR
            (out / "qr").mkdir()
            for d in DiTich.objects.published():
                for fmt in ("png", "svg"):
                    r = c.get(f"/qr/{d.slug}.{fmt}")
                    if r.status_code == 200:
                        (out / "qr" / f"{d.slug}.{fmt}").write_bytes(r.content)
        # static + media
        for src, name in ((settings.BASE_DIR / "static", "static"), (Path(settings.MEDIA_ROOT), "media")):
            if src.exists():
                shutil.copytree(src, out / name, ignore=shutil.ignore_patterns("docs", "*.map"))
        (out / "index.html").write_text(
            f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={prefix}vi/">'
            f'<link rel="canonical" href="{prefix}vi/"><a href="{prefix}vi/">Di tích Vân Đồn</a>', "utf-8")
        self.stdout.write(self.style.SUCCESS(f"Đã xuất {n} trang vào {out}"))
