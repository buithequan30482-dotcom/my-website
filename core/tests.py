import pyotp
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core import middleware as mw
from core.help_content import load_help
from core.models import AdminProfile, AuditLog, HelpArticle, SiteConfig
from heritage.models import DiTich, KhuVuc, TrangThai
from interactions.models import DanhGia, GopY, TrangThaiDuyet

User = get_user_model()
PW = "MatKhauRatManh!2025"


def make_ditich(ma="VD01", ten="Đình Quan Lạn", trang_thai=TrangThai.PUBLISHED, **k):
    kv, _ = KhuVuc.objects.get_or_create(slug="quan-lan", defaults={"ten": "Quan Lạn"})
    return DiTich.objects.create(ma=ma, ten=ten, cap_xep_hang="qg", khu_vuc=kv, dia_chi_moi="Quan Lạn",
                                 tom_tat="Đình làng cổ.", trang_thai=trang_thai, **k)


class OTPFlowTests(TestCase):
    def setUp(self):
        self.su = User.objects.create_superuser("quantri", "qt@example.com", PW)
        self.admin_index = reverse("admin:index")

    def login(self, username="quantri"):
        r = self.client.post(reverse("admin:login"), {"username": username, "password": PW, "next": self.admin_index})
        self.assertEqual(r.status_code, 302)

    def test_superuser_without_otp_forced_to_setup(self):
        self.login()
        r = self.client.get(self.admin_index)
        self.assertRedirects(r, reverse("core:otp_setup"), fetch_redirect_response=False)
        r = self.client.get(reverse("core:otp_setup"))
        self.assertContains(r, "data:image/png;base64,")
        self.assertContains(r, "Bắt buộc")

    def test_setup_with_correct_code_enables_and_grants_access(self):
        self.login()
        self.client.get(reverse("core:otp_setup"))
        prof = AdminProfile.objects.get(user=self.su)
        r = self.client.post(reverse("core:otp_setup"), {"code": "000000"})
        self.assertEqual(r.status_code, 200)  # sai mã
        self.assertFalse(AdminProfile.objects.get(user=self.su).otp_enabled)
        r = self.client.post(reverse("core:otp_setup"), {"code": pyotp.TOTP(prof.otp_secret).now()})
        self.assertRedirects(r, self.admin_index, fetch_redirect_response=False)
        self.assertTrue(AdminProfile.objects.get(user=self.su).otp_enabled)
        self.assertEqual(self.client.get(self.admin_index).status_code, 200)

    def _enable(self, user):
        secret = pyotp.random_base32()
        AdminProfile.objects.update_or_create(user=user, defaults={"otp_secret": secret, "otp_enabled": True})
        return secret

    def test_enabled_user_must_enter_code_after_login(self):
        secret = self._enable(self.su)
        self.login()
        r = self.client.get(self.admin_index)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith(reverse("core:otp_verify")))
        # Không được xem lại mã bí mật khi chưa nhập mã
        r = self.client.get(reverse("core:otp_setup"))
        self.assertTrue(r["Location"].startswith(reverse("core:otp_verify")))
        r = self.client.post(reverse("core:otp_verify"), {"code": pyotp.TOTP(secret).now(), "next": self.admin_index})
        self.assertRedirects(r, self.admin_index, fetch_redirect_response=False)
        self.assertEqual(self.client.get(self.admin_index).status_code, 200)

    def test_staff_with_otp_enabled_also_verified(self):
        staff = User.objects.create_user("bientap", "bt@example.com", PW, is_staff=True)
        self._enable(staff)
        self.login("bientap")
        r = self.client.get(self.admin_index)
        self.assertTrue(r["Location"].startswith(reverse("core:otp_verify")))

    def test_staff_without_otp_not_forced(self):
        User.objects.create_user("bientap", "bt@example.com", PW, is_staff=True)
        self.login("bientap")
        self.assertEqual(self.client.get(self.admin_index).status_code, 200)

    def test_wrong_codes_lock_account(self):
        self._enable(self.su)
        self.login()
        for _ in range(5):
            r = self.client.post(reverse("core:otp_verify"), {"code": "000000"})
        self.assertRedirects(r, reverse("admin:login"), fetch_redirect_response=False)
        self.assertTrue(AdminProfile.objects.get(user=self.su).is_locked())

    def test_self_reset_and_disable_require_current_code(self):
        staff = User.objects.create_user("bientap", "bt@example.com", PW, is_staff=True)
        secret = self._enable(staff)
        self.login("bientap")
        self.client.post(reverse("core:otp_verify"), {"code": pyotp.TOTP(secret).now()})
        self.assertContains(self.client.get(reverse("core:otp_setup")), "Đang bật xác thực 2 lớp")
        self.client.post(reverse("core:otp_disable"), {"code": "000000"})
        self.assertTrue(AdminProfile.objects.get(user=staff).otp_enabled)
        self.client.post(reverse("core:otp_disable"), {"code": pyotp.TOTP(secret).now()})
        self.assertFalse(AdminProfile.objects.get(user=staff).otp_enabled)

    def test_superuser_cannot_disable_only_reset(self):
        secret = self._enable(self.su)
        self.login()
        self.client.post(reverse("core:otp_verify"), {"code": pyotp.TOTP(secret).now()})
        self.client.post(reverse("core:otp_disable"), {"code": pyotp.TOTP(secret).now()})
        self.assertTrue(AdminProfile.objects.get(user=self.su).otp_enabled)
        r = self.client.post(reverse("core:otp_reset"), {"code": pyotp.TOTP(secret).now()})
        prof = AdminProfile.objects.get(user=self.su)
        self.assertFalse(prof.otp_enabled)
        self.assertNotEqual(prof.otp_secret, secret)
        # phiên bị yêu cầu thiết lập lại
        self.assertRedirects(self.client.get(self.admin_index), reverse("core:otp_setup"), fetch_redirect_response=False)

    def test_admin_action_reset_otp_and_unlock(self):
        staff = User.objects.create_user("bientap", "bt@example.com", PW, is_staff=True)
        self._enable(staff)
        AdminProfile.objects.filter(user=staff).update(failed_logins=3)
        self.client.force_login(self.su)
        s = self.client.session
        s["otp_ok"] = True
        s.save()
        url = reverse("admin:auth_user_changelist")
        self.client.post(url, {"action": "reset_otp", "_selected_action": [staff.pk]})
        self.assertFalse(AdminProfile.objects.get(user=staff).otp_enabled)
        from django.utils import timezone
        AdminProfile.objects.filter(user=staff).update(locked_until=timezone.now() + timezone.timedelta(minutes=10))
        self.client.post(url, {"action": "unlock_accounts", "_selected_action": [staff.pk]})
        self.assertFalse(AdminProfile.objects.get(user=staff).is_locked())


class LockoutTests(TestCase):
    def test_locked_after_5_failures(self):
        User.objects.create_user("bientap", "bt@example.com", PW, is_staff=True)
        url = reverse("admin:login")
        for _ in range(5):
            self.client.post(url, {"username": "bientap", "password": "sai-mat-khau"})
        prof = AdminProfile.objects.get(user__username="bientap")
        self.assertTrue(prof.is_locked())
        r = self.client.post(url, {"username": "bientap", "password": PW})
        self.assertEqual(r.status_code, 200)  # vẫn ở trang đăng nhập
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(AuditLog.objects.filter(action="login_fail").exists())
        self.assertContains(r, "tạm khóa")  # thông báo rõ ràng, không phải "sai mật khẩu"
        self.assertContains(r, "vd-locked")

    def test_login_page_shows_lock_hint(self):
        r = self.client.get(reverse("admin:login"))
        self.assertContains(r, "5 lần")
        self.assertContains(r, "15 phút")
        self.assertContains(r, "vd-seal")


class AdminPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.su = User.objects.create_superuser("quantri", "qt@example.com", PW)
        cls.dt = make_ditich()
        make_ditich("VD02", "Đền Cặp Tiên", TrangThai.DRAFT)
        DanhGia.objects.create(di_tich=cls.dt, so_sao=5, noi_dung="Rất đẹp và yên bình.", ten_hien_thi="Khách")
        GopY.objects.create(loai="xuong_cap", di_tich=cls.dt, noi_dung="Tường nứt")
        load_help()

    def setUp(self):
        self.client.force_login(self.su)
        s = self.client.session
        s["otp_ok"] = True
        s.save()

    def test_admin_index_has_tiles(self):
        r = self.client.get(reverse("admin:index"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "vd-tiles")
        self.assertContains(r, "Di tích đã xuất bản")
        self.assertContains(r, "Nhận xét chờ duyệt")
        self.assertContains(r, "Báo xuống cấp chưa xử lý")
        self.assertContains(r, "Việc cần làm")
        self.assertContains(r, "Di tích thiếu tọa độ")
        self.assertContains(r, reverse("dashboard:moderation"))
        self.assertContains(r, "Xin chào")
        cl = reverse("admin:heritage_ditich_changelist")
        for q in ["?toa_do=thieu", "?anh=minh_hoa", "?ban_dich=thieu", "?trang_thai__exact=draft",
                  "?trang_thai__exact=review"]:
            self.assertContains(r, cl + q)
            self.assertEqual(self.client.get(cl + q).status_code, 200)
        self.assertContains(r, reverse("admin:interactions_danhgia_changelist") + "?trang_thai__exact=pending")
        self.assertContains(r, "Kiểm duyệt nhanh")
        self.assertContains(r, "Tài khoản và vai trò")

    def test_index_respects_permissions(self):
        from django.contrib.auth.models import Permission
        u = User.objects.create_user("kiemduyet", "kd@example.com", PW, is_staff=True)
        u.user_permissions.add(Permission.objects.get(codename="view_danhgia"))
        self.client.force_login(u)
        r = self.client.get(reverse("admin:index"))
        self.assertContains(r, "Nhận xét chờ duyệt")
        self.assertNotContains(r, "Di tích đã xuất bản")
        self.assertNotContains(r, "Góp ý mới")

    def test_help_pages(self):
        r = self.client.get(reverse("core:help"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "vd-help-card", count=HelpArticle.objects.count())
        art = HelpArticle.objects.first()
        art.video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        art.save()
        r = self.client.get(reverse("core:help_detail", args=[art.slug]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "youtube-nocookie.com/embed/dQw4w9WgXcQ")
        self.assertContains(r, "data-vd-print")
        self.assertContains(r, "/static/docs/HDSD_Quan_tri.pdf")
        self.assertEqual(self.client.get(reverse("core:help_detail", args=["khong-co"])).status_code, 404)

    def test_siteconfig_singleton(self):
        SiteConfig.get()
        r = self.client.get(reverse("admin:core_siteconfig_changelist"))
        self.assertRedirects(r, reverse("admin:core_siteconfig_change", args=[1]), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("admin:core_siteconfig_add")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:core_siteconfig_delete", args=[1])).status_code, 403)
        r = self.client.get(reverse("admin:core_siteconfig_change", args=[1]))
        self.assertContains(r, "Google Cloud Console")

    def test_siteconfig_edit_writes_audit(self):
        cfg = SiteConfig.get()
        url = reverse("admin:core_siteconfig_change", args=[cfg.pk])
        data = {"site_name": "Di tích Vân Đồn", "tagline": "Khẩu hiệu mới", "owner_name": cfg.owner_name,
                "google_maps_api_key": "", "address": "", "phone": "0203 000 000", "email": "",
                "facebook_url": "", "youtube_url": "", "zalo_url": "", "notify_emails": "a@example.com; b@example.com",
                "pending_threshold": 20, "hero_video_url": "", "_save": "1"}
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["adminform"].form.errors)
        cfg.refresh_from_db()
        self.assertEqual(cfg.notify_emails, "a@example.com, b@example.com")
        row = AuditLog.objects.filter(action="update", object_type="Cấu hình hệ thống").first()
        self.assertIsNotNone(row)
        self.assertIn("tagline", row.changes)
        self.assertEqual(row.username, "quantri")

    def test_auditlog_delete_only_older_than_12_months(self):
        from datetime import timedelta
        from django.utils import timezone
        old = AuditLog.objects.create(action="other", object_repr="cũ", created_at=timezone.now() - timedelta(days=400))
        new = AuditLog.objects.create(action="other", object_repr="mới")
        r = self.client.post(reverse("admin:core_auditlog_changelist"),
                             {"action": "xoa_nhat_ky_cu", "_selected_action": [old.pk, new.pk]})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(AuditLog.objects.filter(pk=old.pk).exists())
        self.assertTrue(AuditLog.objects.filter(pk=new.pk).exists())
        self.assertEqual(self.client.get(reverse("admin:core_auditlog_delete", args=[new.pk])).status_code, 403)
        staff = User.objects.create_user("xem", "x@example.com", PW, is_staff=True)
        from django.contrib.auth.models import Permission
        staff.user_permissions.add(*Permission.objects.filter(codename__in=["view_auditlog", "delete_auditlog"]))
        self.client.force_login(staff)
        r = self.client.get(reverse("admin:core_auditlog_changelist"))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "xoa_nhat_ky_cu")

    def test_user_inline_unlock_button(self):
        from datetime import timedelta
        from django.utils import timezone
        u = User.objects.create_user("bientap", "bt@example.com", PW, is_staff=True)
        AdminProfile.objects.create(user=u, otp_enabled=True, otp_secret=pyotp.random_base32(),
                                    locked_until=timezone.now() + timedelta(minutes=10))
        r = self.client.get(reverse("admin:auth_user_change", args=[u.pk]))
        self.assertContains(r, reverse("admin:core_user_unlock", args=[u.pk]))
        self.assertContains(r, reverse("admin:core_user_otp_reset", args=[u.pk]))
        self.assertEqual(self.client.get(reverse("admin:core_user_unlock", args=[u.pk])).status_code, 403)
        self.client.post(reverse("admin:core_user_unlock", args=[u.pk]))
        self.client.post(reverse("admin:core_user_otp_reset", args=[u.pk]))
        prof = AdminProfile.objects.get(user=u)
        self.assertFalse(prof.is_locked())
        self.assertFalse(prof.otp_enabled)

    def test_auditlog_readonly_and_diff(self):
        mw._local.user, mw._local.ip = self.su, "127.0.0.1"
        try:
            self.dt.ten = "Đình Quan Lạn (sửa)"
            self.dt.save()
        finally:
            mw._local.user, mw._local.ip = None, ""
        logrow = AuditLog.objects.filter(action="update", object_id=str(self.dt.pk)).first()
        self.assertIsNotNone(logrow)
        self.assertIn("ten", logrow.changes)
        self.assertEqual(self.client.get(reverse("admin:core_auditlog_add")).status_code, 403)
        r = self.client.get(reverse("admin:core_auditlog_change", args=[logrow.pk]))
        self.assertContains(r, "vd-diff")
        self.assertEqual(self.client.get(reverse("admin:core_auditlog_changelist") + "?action__exact=update").status_code, 200)

    def test_auditlog_on_danhgia_admin_action(self):
        dg = DanhGia.objects.get()
        self.client.post(reverse("admin:interactions_danhgia_changelist"),
                         {"action": "duyet", "_selected_action": [dg.pk]})
        dg.refresh_from_db()
        self.assertEqual(dg.trang_thai, TrangThaiDuyet.APPROVED)
        self.assertTrue(AuditLog.objects.filter(action="approve", object_id=str(dg.pk), username="quantri").exists())

    def test_user_admin_pages(self):
        r = self.client.get(reverse("admin:auth_user_changelist"))
        self.assertContains(r, "Quản trị hệ thống")
        r = self.client.get(reverse("admin:auth_user_change", args=[self.su.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Kiểm duyệt tương tác")

    def test_otp_setup_page_renders(self):
        r = self.client.get(reverse("core:otp_setup"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "vd-secret")
