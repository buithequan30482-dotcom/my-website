import time

from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import SiteConfig
from heritage.models import DiTich, KhuVuc, TrangThai

from .models import DanhGia, GopY, LichSuXuLy, TrangThaiDuyet, TuCam, YeuThich

User = get_user_model()
PW = "MatKhauRatManh!2025"


def ts(ago=10):
    return signing.dumps(int(time.time()) - ago)


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        kv = KhuVuc.objects.create(ten="Quan Lạn", slug="quan-lan")
        cls.dt = DiTich.objects.create(ma="VD01", ten="Đình Quan Lạn", cap_xep_hang="qg", khu_vuc=kv,
                                       dia_chi_moi="Quan Lạn", tom_tat="Đình làng cổ.", trang_thai=TrangThai.PUBLISHED)
        cls.nhap = DiTich.objects.create(ma="VD02", ten="Đền nháp", cap_xep_hang="tinh", khu_vuc=kv,
                                         dia_chi_moi="Quan Lạn", tom_tat="Nháp.", trang_thai=TrangThai.DRAFT)

    def setUp(self):
        cache.clear()

    @property
    def review_url(self):
        return f"/vi/di-tich/{self.dt.slug}/danh-gia/"

    def review_data(self, **k):
        d = {"so_sao": "5", "noi_dung": "Cảnh quan rất đẹp, di tích được giữ gìn cẩn thận.",
             "ten_hien_thi": "Minh Anh", "email": "", "dien_thoai": "", "website": "", "ts": ts()}
        d.update(k)
        return d


class ReviewTests(Base):
    def test_valid_review_saved_pending_and_hidden_until_approved(self):
        r = self.client.post(self.review_url, self.review_data())
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].endswith("#danh-gia"))
        dg = DanhGia.objects.get()
        self.assertEqual(dg.trang_thai, TrangThaiDuyet.PENDING)
        self.assertEqual(dg.di_tich, self.dt)
        self.assertEqual(dg.ngon_ngu, "vi")
        self.assertFalse(dg.nghi_spam)
        detail = self.dt.get_absolute_url()
        self.assertNotContains(self.client.get(detail), "Cảnh quan rất đẹp, di tích được giữ gìn cẩn thận.")
        dg.trang_thai = TrangThaiDuyet.APPROVED
        dg.phan_hoi = "Cảm ơn bạn đã ghé thăm."
        dg.save()
        r = self.client.get(detail)
        self.assertContains(r, "Cảnh quan rất đẹp, di tích được giữ gìn cẩn thận.")
        self.assertContains(r, "Cảm ơn bạn đã ghé thăm.")

    def test_honeypot_and_too_fast_are_silently_dropped(self):
        self.client.post(self.review_url, self.review_data(website="http://spam.example"))
        self.client.post(self.review_url, self.review_data(ts=ts(ago=0)))
        self.client.post(self.review_url, self.review_data(ts="gia-mao"))
        self.assertEqual(DanhGia.objects.count(), 0)

    def test_rate_limit_5_per_hour(self):
        for i in range(7):
            self.client.post(self.review_url, self.review_data(ten_hien_thi=f"Khách {i}"))
        self.assertEqual(DanhGia.objects.count(), 5)

    def test_validation_short_text_and_consent(self):
        r = self.client.post(self.review_url, self.review_data(noi_dung="ngắn quá"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "ít nhất 20 ký tự")
        r = self.client.post(self.review_url, self.review_data(email="a@example.com"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(DanhGia.objects.count(), 0)
        r = self.client.post(self.review_url, self.review_data(email="a@example.com", dong_y="on"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(DanhGia.objects.get().email, "a@example.com")

    def test_link_and_banned_word_flag_spam(self):
        TuCam.objects.create(tu="cá độ")
        self.client.post(self.review_url, self.review_data(noi_dung="Vào www.example.com để nhận quà, cá độ uy tín nhé."))
        dg = DanhGia.objects.get()
        self.assertTrue(dg.nghi_spam)
        self.assertIn("liên kết", dg.ly_do_nghi)
        self.assertIn("cá độ", dg.ly_do_nghi)

    def test_unpublished_site_404(self):
        r = self.client.post(f"/vi/di-tich/{self.nhap.slug}/danh-gia/", self.review_data())
        self.assertEqual(r.status_code, 404)


class FeedbackTests(Base):
    url = "/vi/gop-y/"

    def data(self, **k):
        d = {"loai": "mong_muon", "di_tich": "", "noi_dung": "Mong có thêm bản thuyết minh tiếng Anh.",
             "ho_ten": "", "email": "", "dien_thoai": "", "website": "", "ts": ts()}
        d.update(k)
        return d

    def test_form_page_and_code_sequence(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        r = self.client.post(self.url, self.data())
        year = timezone.localdate().year
        self.assertRedirects(r, reverse("interactions:feedback_done", kwargs={"ma": f"GY-{year}-00001"}),
                             fetch_redirect_response=False)
        self.client.post(self.url, self.data())
        self.assertEqual(list(GopY.objects.order_by("ma_tra_cuu").values_list("ma_tra_cuu", flat=True)),
                         [f"GY-{year}-00001", f"GY-{year}-00002"])
        self.assertContains(self.client.get(r["Location"]), f"GY-{year}-00001")

    def test_lookup_shows_status_and_reply(self):
        g = GopY.objects.create(loai="hoi_dap", noi_dung="Giờ mở cửa?", phan_hoi="Mở cửa 7h–17h hằng ngày.",
                                trang_thai=GopY.XuLy.XONG)
        r = self.client.get("/vi/tra-cuu-gop-y/", {"ma": g.ma_tra_cuu.lower()})
        self.assertContains(r, "Mở cửa 7h–17h hằng ngày.")
        r = self.client.get("/vi/tra-cuu-gop-y/", {"ma": "GY-1999-99999"})
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Mở cửa 7h–17h hằng ngày.")

    def test_contact_requires_consent_and_valid_email(self):
        r = self.client.post(self.url, self.data(email="khong-hop-le"))
        self.assertEqual(r.status_code, 200)
        r = self.client.post(self.url, self.data(dien_thoai="0912345678"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(GopY.objects.count(), 0)
        r = self.client.post(self.url, self.data(dien_thoai="0912345678", dong_y="on"))
        self.assertEqual(r.status_code, 302)

    def test_degradation_report_notifies(self):
        cfg = SiteConfig.get()
        cfg.notify_emails = "vhxh@example.com"
        cfg.save()
        self.client.post(self.url, self.data(loai="xuong_cap", di_tich=str(self.dt.pk),
                                             noi_dung="Tường bao phía sau có vết nứt lớn."))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("xuống cấp", mail.outbox[0].subject)

    def test_honeypot_feedback(self):
        r = self.client.post(self.url, self.data(website="x"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(GopY.objects.count(), 0)


class WantToGoTests(Base):
    def test_counted_once_per_browser(self):
        url = f"/api/muon-den/{self.dt.slug}/"
        r1 = self.client.post(url)
        r2 = self.client.post(url)
        self.assertEqual(r1.json(), {"count": 1, "created": True})
        self.assertEqual(r2.json(), {"count": 1, "created": False})
        other = self.client_class()
        self.assertEqual(other.post(url).json()["count"], 2)
        self.assertEqual(YeuThich.objects.count(), 2)
        self.assertEqual(self.client.get(url).status_code, 405)


class AdminActionTests(Base):
    def setUp(self):
        super().setUp()
        self.su = User.objects.create_superuser("quantri", "qt@example.com", PW)
        self.client.force_login(self.su)
        s = self.client.session
        s["otp_ok"] = True
        s.save()
        self.dg = [DanhGia.objects.create(di_tich=self.dt, so_sao=i, noi_dung=f"Nhận xét số {i} khá dài.",
                                          ten_hien_thi="Khách", email="nguyenvan@gmail.com", dien_thoai="0912345678")
                   for i in (3, 4, 5)]

    def act(self, model, action, ids):
        return self.client.post(reverse(f"admin:interactions_{model}_changelist"),
                                {"action": action, "_selected_action": ids})

    def test_review_actions(self):
        self.act("danhgia", "duyet", [self.dg[0].pk, self.dg[1].pk])
        self.act("danhgia", "danh_dau_spam", [self.dg[2].pk])
        a, b, c = [DanhGia.objects.get(pk=d.pk) for d in self.dg]
        self.assertEqual((a.trang_thai, b.trang_thai, c.trang_thai), ("approved", "approved", "spam"))
        self.assertEqual(a.nguoi_duyet, self.su)
        self.assertIsNotNone(a.ngay_duyet)
        self.assertTrue(c.nghi_spam)
        self.act("danhgia", "an", [a.pk])
        self.assertEqual(DanhGia.objects.get(pk=a.pk).trang_thai, "hidden")
        self.assertContains(self.client.get(self.dt.get_absolute_url()), "Nhận xét số 4 khá dài.")

    def test_review_changelist_and_masking(self):
        r = self.client.get(reverse("admin:interactions_danhgia_changelist"))
        self.assertContains(r, reverse("dashboard:moderation"))
        self.assertContains(r, "vd-stars")
        r = self.client.get(reverse("admin:interactions_danhgia_change", args=[self.dg[0].pk]))
        self.assertContains(r, "nguyenvan@gmail.com")  # superuser thấy đủ
        from django.contrib.auth.models import Group
        mod = User.objects.create_user("kiemduyet", "kd@example.com", PW, is_staff=True)
        mod.groups.add(Group.objects.get_or_create(name="Kiểm duyệt tương tác")[0])
        from django.contrib.auth.models import Permission
        mod.user_permissions.add(*Permission.objects.filter(codename__in=["view_danhgia", "change_danhgia"]))
        self.client.force_login(mod)
        r = self.client.get(reverse("admin:interactions_danhgia_change", args=[self.dg[0].pk]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "nguyenvan@gmail.com")
        self.assertContains(r, "ng***@gmail.com")
        self.assertContains(r, "0912***678")

    def test_gopy_actions_and_history(self):
        g = GopY.objects.create(loai="xuong_cap", di_tich=self.dt, noi_dung="Mái ngói xô lệch.")
        r = self.client.get(reverse("admin:interactions_gopy_changelist"))
        self.assertContains(r, "Báo di tích xuống cấp")
        self.act("gopy", "nhan_xu_ly", [g.pk])
        g.refresh_from_db()
        self.assertEqual((g.trang_thai, g.nguoi_xu_ly), ("dang", self.su))
        self.act("gopy", "danh_dau_xong", [g.pk])
        g.refresh_from_db()
        self.assertEqual(g.trang_thai, "xong")
        self.assertIsNotNone(g.ngay_xu_ly)
        self.assertEqual(LichSuXuLy.objects.filter(gop_y=g).count(), 2)
        self.act("gopy", "dong", [g.pk])
        self.assertEqual(GopY.objects.get(pk=g.pk).trang_thai, "dong")

    def test_gopy_change_form_logs_history(self):
        g = GopY.objects.create(loai="hoi_dap", noi_dung="Giờ mở cửa?")
        url = reverse("admin:interactions_gopy_change", args=[g.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        r = self.client.post(url, {"trang_thai": "xong", "nguoi_xu_ly": self.su.pk, "ghi_chu_noi_bo": "",
                                   "phan_hoi": "Mở cửa 7h–17h.", "cong_khai": "on",
                                   "lich_su-TOTAL_FORMS": "0", "lich_su-INITIAL_FORMS": "0",
                                   "lich_su-MIN_NUM_FORMS": "0", "lich_su-MAX_NUM_FORMS": "1000", "_save": "1"})
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["adminform"].form.errors)
        g.refresh_from_db()
        self.assertTrue(g.cong_khai)
        note = LichSuXuLy.objects.get(gop_y=g).noi_dung
        self.assertIn("Mới → Đã xử lý", note)
        self.assertIn("Người xử lý", note)
        self.assertIn("phản hồi", note)

    def test_public_requires_reply(self):
        g = GopY.objects.create(loai="hoi_dap", noi_dung="Giờ mở cửa?")
        url = reverse("admin:interactions_gopy_change", args=[g.pk])
        r = self.client.post(url, {"trang_thai": "moi", "nguoi_xu_ly": "", "ghi_chu_noi_bo": "", "phan_hoi": "",
                                   "cong_khai": "on", "lich_su-TOTAL_FORMS": "0", "lich_su-INITIAL_FORMS": "0",
                                   "lich_su-MIN_NUM_FORMS": "0", "lich_su-MAX_NUM_FORMS": "1000"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(GopY.objects.get(pk=g.pk).cong_khai)

    def test_tucam_bulk_add(self):
        TuCam.objects.create(tu="lừa đảo")
        url = reverse("admin:interactions_tucam_bulk")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {"danh_sach": "cá độ\nLừa đảo\n\n  casino  \n赌博"})
        self.assertEqual(sorted(TuCam.objects.values_list("tu", flat=True)), sorted(["lừa đảo", "cá độ", "casino", "赌博"]))
