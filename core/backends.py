from django.contrib.auth.backends import ModelBackend


class LockoutBackend(ModelBackend):
    """Từ chối đăng nhập khi tài khoản đang bị khóa tạm (sai mật khẩu quá 5 lần)."""

    def user_can_authenticate(self, user):
        prof = getattr(user, "admin_profile", None)
        if prof is not None and prof.is_locked():
            return False
        return super().user_can_authenticate(user)
