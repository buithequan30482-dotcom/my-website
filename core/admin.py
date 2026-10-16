"""Quản trị hệ thống: cấu hình, nhật ký thao tác, hướng dẫn, tài khoản (TR FR-A01, A12, A13, H03)."""
import json
from datetime import timedelta

from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from .models import AdminProfile, AuditLog, HelpArticle, SiteConfig
from .signals import log

User = get_user_model()


# ---------------------------------------------------------------- Cấu hình hệ thống (singleton)
MAPS_HELP = mark_safe(
    "Cách lấy khóa: (1) đăng nhập <a href='https://console.cloud.google.com/' target='_blank' rel='noopener'>"
    "Google Cloud Console</a> bằng tài khoản của cơ quan, tạo dự án; (2) bật <em>Maps JavaScript API</em>, "
    "<em>Maps Embed API</em>, <em>Places API</em>; (3) tạo API key, giới hạn theo tên miền website (HTTP referrers) "
    "và chỉ 3 API trên; (4) đặt hạn mức và cảnh báo ngân sách. Để trống: website tự dùng bản đồ OpenStreetMap. "
    "Xem thêm bài hướng dẫn số 8."
)


class SiteConfigForm(forms.ModelForm):
    class Meta:
        model = SiteConfig
        fields = "__all__"
        widgets = {"google_maps_api_key": forms.TextInput(attrs={"autocomplete": "off", "spellcheck": "false",
                                                                 "class": "vTextField"})}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["google_maps_api_key"].help_text = MAPS_HELP

    def clean_notify_emails(self):
        raw = self.cleaned_data.get("notify_emails") or ""
        emails = [e.strip() for e in raw.replace(";", ",").split(",") if e.strip()]
        bad = []
        for e in emails:
            try:
                forms.EmailField().clean(e)
            except forms.ValidationError:
                bad.append(e)
        if bad:
            raise forms.ValidationError("Email không hợp lệ: " + ", ".join(bad))
        return ", ".join(emails)


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    form = SiteConfigForm
    readonly_fields = ["updated_at"]
    fieldsets = [
        ("Thông tin chung", {"fields": ["site_name", "tagline", "owner_name", "hero_video_url"]}),
        ("Bản đồ", {"fields": ["google_maps_api_key"],
                    "description": "Bản đồ trên website dùng Google Maps nếu có khóa, nếu không dùng OpenStreetMap."}),
        ("Liên hệ & mạng xã hội", {"fields": ["address", "phone", "email", "facebook_url", "youtube_url", "zalo_url"],
                                   "description": "Hiển thị ở chân trang và trang Liên hệ."}),
        ("Thông báo", {
            "fields": ["notify_emails", "pending_threshold"],
            "description": "Gửi email khi có báo di tích xuống cấp hoặc khi số nhận xét chờ duyệt đạt ngưỡng.",
        }),
        ("Khác", {"fields": ["updated_at"], "classes": ["collapse"]}),
    ]

    def has_add_permission(self, request):
        return False  # chỉ một bản ghi, tạo tự động bởi SiteConfig.get()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = SiteConfig.get()
        return HttpResponseRedirect(reverse("admin:core_siteconfig_change", args=[obj.pk]))

    def response_change(self, request, obj):
        if "_continue" not in request.POST and "_save" in request.POST:
            self.message_user(request, "Đã lưu cấu hình hệ thống.", messages.SUCCESS)
            return HttpResponseRedirect(reverse("admin:core_siteconfig_change", args=[obj.pk]))
        return super().response_change(request, obj)


# ---------------------------------------------------------------- Nhật ký thao tác (chỉ đọc)
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["thoi_gian", "username_col", "action_col", "object_type", "object_repr", "ip"]
    list_filter = ["action", ("user", admin.RelatedOnlyFieldListFilter), "object_type", "created_at"]
    search_fields = ["username", "object_repr", "object_id", "object_type", "ip"]
    date_hierarchy = "created_at"
    list_per_page = 50
    fields = ["created_at", "username", "action", "object_type", "object_id", "object_repr", "ip", "changes_table"]
    readonly_fields = fields

    ACTION_TONE = {"delete": "son", "login_fail": "son", "hide": "da", "publish": "ngoc", "approve": "ngoc",
                   "create": "ngoc", "update": "dong", "login": "da", "export": "da", "import": "dong"}

    @admin.display(description="Thời gian", ordering="created_at")
    def thoi_gian(self, obj):
        return timezone.localtime(obj.created_at).strftime("%d/%m/%Y %H:%M:%S")

    @admin.display(description="Tài khoản", ordering="username")
    def username_col(self, obj):
        return obj.username or "—"

    @admin.display(description="Hành động", ordering="action")
    def action_col(self, obj):
        return format_html('<span class="vd-badge vd-badge-{}">{}</span>',
                           self.ACTION_TONE.get(obj.action, "da"), obj.get_action_display())

    @admin.display(description="Thay đổi")
    def changes_table(self, obj):
        ch = obj.changes
        if not ch:
            return "—"
        if not isinstance(ch, dict):
            return format_html("<pre>{}</pre>", json.dumps(ch, ensure_ascii=False, indent=2))
        rows = []
        for k, v in ch.items():
            old, new = (v + [""])[:2] if isinstance(v, list) else ("", v)
            rows.append((k, old if old not in ("None", None) else "—", new if new not in ("None", None) else "—"))
        body = format_html_join("", '<tr><td class="field">{}</td><td class="old">{}</td><td class="new">{}</td></tr>', rows)
        return format_html('<table class="vd-diff"><thead><tr><th>Trường</th><th>Trước</th><th>Sau</th></tr></thead>'
                           "<tbody>{}</tbody></table>", body)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    # Chỉ Quản trị hệ thống được xóa, và chỉ nhật ký cũ hơn 12 tháng (TR FR-A12: lưu tối thiểu 12 tháng).
    RETAIN_DAYS = 365

    def _cutoff(self):
        return timezone.now() - timedelta(days=self.RETAIN_DAYS)

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_superuser:
            return False
        return obj is None or obj.created_at < self._cutoff()

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    @admin.action(description="Xóa các mục đã chọn cũ hơn 12 tháng", permissions=["delete"])
    def xoa_nhat_ky_cu(self, request, queryset):
        old = queryset.filter(created_at__lt=self._cutoff())
        n = old.count()
        skipped = queryset.count() - n
        old.delete()
        if n:
            log("delete", user=request.user, repr_=f"Xóa {n} mục nhật ký thao tác cũ hơn 12 tháng")
        msg = f"Đã xóa {n} mục nhật ký."
        if skipped:
            msg += f" Giữ lại {skipped} mục chưa đủ 12 tháng."
        self.message_user(request, msg, messages.SUCCESS if n else messages.WARNING)

    actions = ["xoa_nhat_ky_cu"]


# ---------------------------------------------------------------- Hướng dẫn sử dụng
class HelpArticleForm(forms.ModelForm):
    class Meta:
        model = HelpArticle
        fields = "__all__"
        widgets = {
            "body": forms.Textarea(attrs={"rows": 28, "cols": 110, "style": "font-family: var(--font-family-monospace); font-size: 13px; width: 100%; max-width: 980px;"}),
            "summary": forms.TextInput(attrs={"class": "vTextField", "style": "width: 100%; max-width: 640px"}),
            "title": forms.TextInput(attrs={"class": "vTextField", "style": "width: 100%; max-width: 640px"}),
        }
        help_texts = {
            "body": "Nội dung HTML: dùng <h3> cho tiêu đề mục, <ol>/<li> cho các bước, <strong> để nhấn mạnh.",
            "video_url": "Dán liên kết YouTube (ví dụ https://www.youtube.com/watch?v=...) – video sẽ được nhúng ở đầu bài.",
            "order": "Số nhỏ hiện trước.",
            "slug": "Đường dẫn của bài, chỉ gồm chữ không dấu, số và dấu gạch ngang.",
        }


@admin.register(HelpArticle)
class HelpArticleAdmin(admin.ModelAdmin):
    form = HelpArticleForm
    list_display = ["order", "title", "summary", "has_video", "view_link"]
    list_display_links = ["title"]
    list_editable = ["order"]
    search_fields = ["title", "summary", "body"]
    prepopulated_fields = {"slug": ["title"]}
    fields = ["title", "slug", "order", "summary", "video_url", "body"]

    @admin.display(description="Video", boolean=True)
    def has_video(self, obj):
        return bool(obj.video_url)

    @admin.display(description="Xem")
    def view_link(self, obj):
        return format_html('<a href="{}">Xem bài</a>', reverse("core:help_detail", args=[obj.slug]))


# ---------------------------------------------------------------- Tài khoản
ROLE_HELP = mark_safe(
    "<strong>Vai trò</strong> (một người có thể nhiều vai trò): "
    "<em>Biên tập viên</em> – thêm, sửa di tích, ảnh, video, tuyến, lễ hội, tin tức, gửi duyệt; "
    "<em>Duyệt nội dung</em> – thêm quyền xuất bản / ẩn, xóa; "
    "<em>Kiểm duyệt tương tác</em> – duyệt nhận xét, xử lý góp ý, xem thống kê; "
    "<em>Quản trị hệ thống</em> – chọn ô <em>Superuser status</em> (toàn quyền, bắt buộc xác thực 2 lớp). "
    "Mọi người dùng khu quản trị phải chọn ô <em>Staff status</em>."
)


class AdminProfileInline(admin.StackedInline):
    model = AdminProfile
    can_delete = False
    extra = 0
    max_num = 1
    verbose_name = verbose_name_plural = "Bảo mật tài khoản"
    fields = ["otp_status", "lock_status", "failed_logins"]
    readonly_fields = fields

    def get_fields(self, request, obj=None):
        return self.fields + (["thao_tac"] if request.user.is_superuser else [])

    def get_readonly_fields(self, request, obj=None):
        return self.get_fields(request, obj)

    @admin.display(description="Thao tác")
    def thao_tac(self, obj):
        if not obj or not obj.pk:
            return "—"
        def btn(url_name, label, cls=""):
            return format_html('<button type="submit" class="vd-btn {}" formaction="{}" formmethod="post" '
                               'formnovalidate>{}</button>', cls, reverse(url_name, args=[obj.user_id]), label)
        parts = []
        if obj.otp_enabled or obj.otp_secret:
            parts.append(btn("admin:core_user_otp_reset", "Đặt lại xác thực 2 lớp"))
        if obj.is_locked() or obj.failed_logins:
            parts.append(btn("admin:core_user_unlock", "Mở khóa tài khoản", "vd-btn-primary"))
        if not parts:
            return format_html('<span class="vd-quiet">Không cần thao tác.</span>')
        return format_html('<div style="display:flex;gap:8px;flex-wrap:wrap">{}</div>'
                           '<div class="help">Đặt lại 2 lớp khi người dùng mất / đổi điện thoại; mở khóa khi bị khóa do '
                           'nhập sai mật khẩu. Các thay đổi chưa lưu khác trên trang sẽ không được lưu.</div>',
                           mark_safe(" ".join(parts)))

    @admin.display(description="Xác thực 2 lớp")
    def otp_status(self, obj):
        if obj.otp_enabled:
            return format_html('<span class="vd-badge vd-badge-ngoc">Đã bật</span>')
        return format_html('<span class="vd-badge vd-badge-da">Chưa bật</span>')

    @admin.display(description="Khóa tạm")
    def lock_status(self, obj):
        if obj.is_locked():
            return format_html('<span class="vd-badge vd-badge-son">Đang khóa đến {}</span>',
                               timezone.localtime(obj.locked_until).strftime("%H:%M %d/%m/%Y"))
        return "Không"

    def has_add_permission(self, request, obj=None):
        return False


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:  # pragma: no cover
    pass


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [AdminProfileInline]
    list_display = ["username", "full_name", "email", "roles", "is_active", "is_staff", "otp_col", "lock_col", "lan_cuoi"]
    list_filter = ["is_staff", "is_superuser", "is_active", "groups", "admin_profile__otp_enabled"]
    actions = ["unlock_accounts", "reset_otp"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("admin_profile").prefetch_related("groups")

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "groups" in form.base_fields:
            form.base_fields["groups"].help_text = ROLE_HELP
            form.base_fields["groups"].label = "Vai trò (nhóm quyền)"
        if "is_superuser" in form.base_fields:
            form.base_fields["is_superuser"].help_text = "Quản trị hệ thống: có mọi quyền, bắt buộc bật xác thực 2 lớp."
        if "is_staff" in form.base_fields:
            form.base_fields["is_staff"].help_text = "Bắt buộc với mọi tài khoản cần đăng nhập khu quản trị."
        return form

    @admin.display(description="Đăng nhập lần cuối", ordering="last_login")
    def lan_cuoi(self, obj):
        return timezone.localtime(obj.last_login).strftime("%d/%m/%Y %H:%M") if obj.last_login else "—"

    @admin.display(description="Họ tên")
    def full_name(self, obj):
        return obj.get_full_name() or "—"

    @admin.display(description="Vai trò")
    def roles(self, obj):
        names = [g.name for g in obj.groups.all()]
        parts = []
        if obj.is_superuser:
            parts.append(format_html('<span class="vd-badge vd-badge-solid-son">Quản trị hệ thống</span>'))
        parts += [format_html('<span class="vd-badge vd-badge-ngoc">{}</span>', n) for n in names]
        return mark_safe(" ".join(parts)) if parts else "—"

    @admin.display(description="2 lớp")
    def otp_col(self, obj):
        prof = getattr(obj, "admin_profile", None)
        on = bool(prof and prof.otp_enabled)
        return format_html('<span class="vd-badge vd-badge-{}">{}</span>', "ngoc" if on else "da", "Bật" if on else "Tắt")

    @admin.display(description="Khóa tạm")
    def lock_col(self, obj):
        prof = getattr(obj, "admin_profile", None)
        if prof and prof.is_locked():
            return format_html('<span class="vd-badge vd-badge-son">Đang khóa</span>')
        return ""

    def get_urls(self):
        from django.urls import path
        w = self.admin_site.admin_view
        return [
            path("<int:user_id>/dat-lai-2-lop/", w(self.single_otp_reset), name="core_user_otp_reset"),
            path("<int:user_id>/mo-khoa/", w(self.single_unlock), name="core_user_unlock"),
        ] + super().get_urls()

    def _single(self, request, user_id, action):
        from django.core.exceptions import PermissionDenied
        from django.shortcuts import get_object_or_404
        if request.method != "POST" or not request.user.is_superuser:
            raise PermissionDenied
        action(self, request, User.objects.filter(pk=get_object_or_404(User, pk=user_id).pk))
        return HttpResponseRedirect(reverse("admin:auth_user_change", args=[user_id]))

    def single_otp_reset(self, request, user_id):
        return self._single(request, user_id, UserAdmin.reset_otp)

    def single_unlock(self, request, user_id):
        return self._single(request, user_id, UserAdmin.unlock_accounts)

    def _need_superuser(self, request):
        if not request.user.is_superuser:
            self.message_user(request, "Chỉ Quản trị hệ thống được thực hiện thao tác này.", messages.ERROR)
            return False
        return True

    @admin.action(description="Mở khóa tài khoản (bị khóa do đăng nhập sai)")
    def unlock_accounts(self, request, queryset):
        if not self._need_superuser(request):
            return
        n = 0
        for u in queryset:
            prof, _ = AdminProfile.objects.get_or_create(user=u)
            prof.locked_until, prof.failed_logins = None, 0
            prof.save(update_fields=["locked_until", "failed_logins"])
            log("other", u, repr_=f"Mở khóa tài khoản: {u.username}")
            n += 1
        self.message_user(request, f"Đã mở khóa {n} tài khoản.", messages.SUCCESS)

    @admin.action(description="Đặt lại xác thực 2 lớp (khi người dùng mất điện thoại)")
    def reset_otp(self, request, queryset):
        if not self._need_superuser(request):
            return
        n = 0
        for u in queryset:
            prof, _ = AdminProfile.objects.get_or_create(user=u)
            prof.otp_enabled, prof.otp_secret = False, ""
            prof.save(update_fields=["otp_enabled", "otp_secret"])
            log("other", u, repr_=f"Đặt lại xác thực 2 lớp: {u.username}")
            n += 1
        self.message_user(request, f"Đã đặt lại xác thực 2 lớp cho {n} tài khoản. Lần đăng nhập tới, "
                                   "người dùng thiết lập lại bằng mã QR mới.", messages.SUCCESS)


admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name", "member_count"]
    search_fields = ["name"]
    filter_horizontal = ["permissions"]

    @admin.display(description="Số thành viên")
    def member_count(self, obj):
        return obj.user_set.count()


# ---------------------------------------------------------------- Đăng nhập: báo rõ khi tài khoản bị khóa tạm
from django.contrib.admin.forms import AdminAuthenticationForm  # noqa: E402
from django.core.exceptions import ValidationError  # noqa: E402


class VDAdminLoginForm(AdminAuthenticationForm):
    error_messages = {
        **AdminAuthenticationForm.error_messages,
        "invalid_login": "Tên đăng nhập hoặc mật khẩu không đúng. Lưu ý: mật khẩu phân biệt chữ hoa, chữ thường.",
        "locked": "Tài khoản đang tạm khóa do nhập sai mật khẩu nhiều lần. Vui lòng thử lại sau khoảng %(minutes)s phút "
                  "(lúc %(until)s) hoặc liên hệ Quản trị hệ thống để được mở khóa.",
    }

    def _locked_error(self):
        username = self.cleaned_data.get("username") or self.data.get("username") or ""
        prof = AdminProfile.objects.filter(user__username=username).first() if username else None
        if prof and prof.is_locked():
            mins = max(1, int((prof.locked_until - timezone.now()).total_seconds() // 60) + 1)
            return ValidationError(self.error_messages["locked"], code="locked", params={
                "minutes": mins, "until": timezone.localtime(prof.locked_until).strftime("%H:%M")})
        return None

    def clean(self):
        err = self._locked_error()
        if err:  # không thử mật khẩu khi đang khóa (không gia hạn khóa, không lộ mật khẩu đúng/sai)
            raise err
        try:
            return super().clean()
        except ValidationError:
            err = self._locked_error()  # lần sai thứ LOGIN_MAX_FAILS vừa kích hoạt khóa
            if err:
                raise err
            raise


admin.site.login_form = VDAdminLoginForm
admin.site.login_template = "admin/login.html"
