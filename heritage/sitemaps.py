from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import DiTich, TinTuc, TrangTinh, TuyenThamQuan


class I18nSitemap(Sitemap):
    i18n = True
    alternates = True
    x_default = True


class SiteSitemap(I18nSitemap):
    changefreq = "monthly"
    priority = 0.9

    def items(self):
        return DiTich.objects.published()

    def lastmod(self, o):
        return o.ngay_sua


class RouteSitemap(I18nSitemap):
    def items(self):
        return TuyenThamQuan.objects.published()


class NewsSitemap(I18nSitemap):
    def items(self):
        return TinTuc.objects.published()


class PageSitemap(I18nSitemap):
    def items(self):
        return TrangTinh.objects.all()

    def location(self, o):
        return reverse("heritage:page", kwargs={"slug": o.slug})


class StaticSitemap(I18nSitemap):
    priority = 1.0

    def items(self):
        return ["heritage:home", "heritage:list", "heritage:map", "heritage:routes", "heritage:festivals",
                "heritage:useful", "interactions:feedback"]

    def location(self, name):
        return reverse(name)


sitemaps = {"static": StaticSitemap, "ditich": SiteSitemap, "tuyen": RouteSitemap, "tin": NewsSitemap, "trang": PageSitemap}
