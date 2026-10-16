"""Kiểm thử cổng công khai (TR 5.1, NFR-04)."""
from django.test import TestCase, override_settings

from core.utils import clean_html, parse_coordinates, strip_accents
from heritage.models import DiemDiTich, DiTich, KhuVuc, LoaiHinh, TrangThai


class UtilsTests(TestCase):
    def test_strip_accents(self):
        self.assertEqual(strip_accents("Đền Cửa Ông"), "den cua ong")

    def test_parse_dms_and_decimal(self):
        self.assertEqual(parse_coordinates('20°53\'49.3"N 107°18\'33.7"E')[:2], (20.897028, 107.309361))
        self.assertEqual(parse_coordinates("20.897028, 107.309361")[:2], (20.897028, 107.309361))
        lat, lng, note = parse_coordinates('20°48\'60.0"N 107°21\'10.0"E')
        self.assertAlmostEqual(lat, 20.816667, places=5)
        self.assertTrue(note)

    def test_clean_html_removes_script(self):
        out = clean_html('<h3>Lịch sử</h3><script>alert(1)</script><p onclick="x">a</p>')
        self.assertNotIn("script", out)
        self.assertNotIn("onclick", out)
        self.assertIn("<h3>Lịch sử</h3>", out)


@override_settings(ALLOWED_HOSTS=["testserver"])
class PublicPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        kv = KhuVuc.objects.create(ten="Quan Lạn", slug="quan-lan", la_dao=True, dao="Quan Lạn")
        lh = LoaiHinh.objects.create(ten="Lịch sử", slug="lich-su")
        cls.d = DiTich.objects.create(ma="VD99", ten="Đình Quan Lạn", ten_vi="Đình Quan Lạn", cap_xep_hang="qgdb",
                                      khu_vuc=kv, dia_chi_moi="Thôn Quan Lạn 1", tom_tat="Tóm tắt thử",
                                      noi_dung="<h3>Lịch sử</h3><p>Nội dung</p>", trang_thai=TrangThai.PUBLISHED)
        cls.d.loai_hinh.add(lh)
        DiemDiTich.objects.create(di_tich=cls.d, ten="Đình", vi_do=20.876, kinh_do=107.494, diem_chinh=True)
        DiTich.objects.create(ma="VD98", ten="Nháp", khu_vuc=kv, cap_xep_hang="kiemke", dia_chi_moi="x",
                              tom_tat="y", trang_thai=TrangThai.DRAFT)

    def setUp(self):
        self.client.defaults["HTTP_USER_AGENT"] = "Mozilla/5.0"

    def test_pages_all_languages(self):
        for lang in ("vi", "en", "zh-hans"):
            for path in ("", "di-tich/", "ban-do/", "tuyen-tham-quan/", "le-hoi-su-kien/", "thong-tin-huu-ich/",
                         "gop-y/", f"di-tich/{self.d.slug}/"):
                r = self.client.get(f"/{lang}/{path}")
                self.assertEqual(r.status_code, 200, f"/{lang}/{path}")

    def test_draft_hidden(self):
        r = self.client.get("/vi/di-tich/")
        self.assertContains(r, "Đình Quan Lạn")
        self.assertNotContains(r, "Nháp")

    def test_search_without_accents(self):
        r = self.client.get("/vi/di-tich/?q=dinh%20quan%20lan")
        self.assertContains(r, "Đình Quan Lạn")
        self.assertEqual(self.client.get("/api/goi-y/?q=quan lan").json()["items"][0]["ten"], "Đình Quan Lạn")

    def test_filters(self):
        self.assertContains(self.client.get("/vi/di-tich/?cap=qgdb"), "Đình Quan Lạn")
        self.assertNotContains(self.client.get("/vi/di-tich/?cap=qg"), "card-body")

    def test_detail_seo_and_map(self):
        r = self.client.get(f"/vi/di-tich/{self.d.slug}/")
        self.assertContains(r, "application/ld+json")
        self.assertContains(r, "TouristAttraction")
        self.assertContains(r, "maps/dir/?api=1&amp;destination=20.876")
        self.assertContains(r, 'hreflang="en"')

    def test_qr_sitemap_robots_health(self):
        self.assertEqual(self.client.get(f"/qr/{self.d.slug}.png")["Content-Type"], "image/png")
        self.assertEqual(self.client.get(f"/qr/{self.d.slug}.svg")["Content-Type"], "image/svg+xml")
        self.assertContains(self.client.get("/sitemap.xml"), self.d.slug)
        self.assertContains(self.client.get("/robots.txt"), "Disallow")
        self.assertEqual(self.client.get("/healthz").status_code, 200)

    def test_pageview_counted_not_for_bots(self):
        from interactions.models import LuotXem
        self.client.get(f"/vi/di-tich/{self.d.slug}/")
        self.client.get(f"/vi/di-tich/{self.d.slug}/", HTTP_USER_AGENT="Googlebot/2.1")
        self.assertEqual(sum(LuotXem.objects.values_list("so_luot", flat=True)), 1)

    def test_security_headers(self):
        r = self.client.get("/vi/")
        self.assertIn("Content-Security-Policy", r)
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
