from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .images import delete_files, process_image
from .models import HinhAnh


@receiver(post_save, sender=HinhAnh)
def _process(sender, instance, created, **kw):
    """Sinh biến thể WebP lần đầu (hoặc khi bien_the bị xóa để yêu cầu xử lý lại)."""
    if instance.tep and not instance.bien_the:
        instance._warnings = process_image(instance)
        HinhAnh.objects.filter(pk=instance.pk).update(
            tep=instance.tep.name, rong=instance.rong, cao=instance.cao, bien_the=instance.bien_the)


@receiver(post_delete, sender=HinhAnh)
def _cleanup(sender, instance, **kw):
    delete_files(instance)
