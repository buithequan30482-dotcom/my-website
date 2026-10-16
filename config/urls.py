from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.i18n import set_language

from core.health import healthz

admin.site.site_header = "Quản trị Website Di tích Vân Đồn"
admin.site.site_title = "Quản trị Di tích Vân Đồn"
admin.site.index_title = "Bảng điều khiển"

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path(settings.ADMIN_URL + "he-thong/", include("core.urls")),
    path(settings.ADMIN_URL + "thong-ke/", include("dashboard.urls")),
    path(settings.ADMIN_URL, admin.site.urls),
    path("i18n/setlang/", set_language, name="set_language"),
    path("", include("interactions.api_urls")),
]
urlpatterns += i18n_patterns(
    path("", include("heritage.urls")),
    path("", include("interactions.urls")),
    prefix_default_language=True,
)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
