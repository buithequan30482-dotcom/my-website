from django.urls import path

from heritage import views as hv
from heritage.sitemaps import sitemaps
from django.contrib.sitemaps.views import sitemap

from . import views

urlpatterns = [
    path("api/muon-den/<slug:slug>/", views.want_to_go, name="want_to_go"),
    path("api/goi-y/", hv.suggest, name="suggest"),
    path("qr/<slug:slug>.<str:fmt>", hv.qr_code, name="qr"),
    path("d/<slug:slug>/", hv.short_link, name="short_link"),
    path("robots.txt", hv.robots),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
]
