from modeltranslation.translator import TranslationOptions, register

from .models import SiteConfig


@register(SiteConfig)
class SiteConfigTR(TranslationOptions):
    fields = ("site_name", "tagline", "owner_name", "address")
