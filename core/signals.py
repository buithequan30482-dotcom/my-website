"""Nhật ký thao tác và khóa tài khoản khi đăng nhập sai nhiều lần."""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .middleware import current_ip, current_user
from .models import AdminProfile, AuditLog

TRACKED = {"heritage", "interactions", "core"}
SKIP_MODELS = {"AuditLog", "LuotXem", "YeuThich", "AdminProfile", "LichSuXuLy"}


def log(action, obj=None, changes=None, user=None, repr_=None):
    user = user or current_user()
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    AuditLog.objects.create(
        user=user, username=getattr(user, "username", "") or "", action=action,
        object_type=obj._meta.verbose_name if obj is not None else "",
        object_id=str(getattr(obj, "pk", "") or ""), object_repr=(repr_ or str(obj or ""))[:300],
        changes=changes, ip=current_ip(),
    )


def _tracked(sender):
    return sender._meta.app_label in TRACKED and sender.__name__ not in SKIP_MODELS


@receiver(pre_save)
def _snapshot(sender, instance, **kw):
    if not _tracked(sender) or not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    instance._old_values = {f.attname: getattr(old, f.attname) for f in sender._meta.concrete_fields}


@receiver(post_save)
def _saved(sender, instance, created, **kw):
    if not _tracked(sender) or current_user() is None:
        return
    if created:
        log("create", instance)
        return
    old = getattr(instance, "_old_values", {})
    changes = {}
    for f in sender._meta.concrete_fields:
        if f.attname in ("search_text", "ngay_sua", "luot_xem", "updated_at"):
            continue
        a, b = old.get(f.attname), getattr(instance, f.attname)
        if a != b:
            changes[f.attname] = [str(a)[:200], str(b)[:200]]
    if changes:
        action = "update"
        if "trang_thai" in changes:
            new = changes["trang_thai"][1]
            action = {"published": "publish", "approved": "approve", "hidden": "hide"}.get(new, "update")
        log(action, instance, changes)


@receiver(post_delete)
def _deleted(sender, instance, **kw):
    if _tracked(sender) and current_user() is not None:
        log("delete", instance)


@receiver(user_logged_in)
def _login(sender, request, user, **kw):
    prof, _ = AdminProfile.objects.get_or_create(user=user)
    prof.failed_logins = 0
    prof.locked_until = None
    prof.save(update_fields=["failed_logins", "locked_until"])
    log("login", user=user, repr_=f"Đăng nhập: {user.username}")


@receiver(user_login_failed)
def _login_failed(sender, credentials, request=None, **kw):
    User = get_user_model()
    username = credentials.get("username", "")
    log("login_fail", user=None, repr_=f"Đăng nhập sai: {username}"[:300])
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return
    prof, _ = AdminProfile.objects.get_or_create(user=user)
    prof.failed_logins += 1
    if prof.failed_logins >= settings.LOGIN_MAX_FAILS:
        prof.locked_until = timezone.now() + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
        prof.failed_logins = 0
    prof.save()
