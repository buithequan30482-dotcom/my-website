from django.urls import path

from . import views

app_name = "heritage"
urlpatterns = [
    path("", views.home, name="home"),
    path("di-tich/", views.site_list, name="list"),
    path("di-tich/<slug:slug>/", views.site_detail, name="detail"),
    path("ban-do/", views.map_page, name="map"),
    path("tuyen-tham-quan/", views.routes, name="routes"),
    path("tuyen-tham-quan/<slug:slug>/", views.route_detail, name="route"),
    path("le-hoi-su-kien/", views.festivals, name="festivals"),
    path("thong-tin-huu-ich/", views.useful, name="useful"),
    path("tin-tuc/", views.news, name="news"),
    path("tin-tuc/<slug:slug>/", views.news_detail, name="news_detail"),
    path("trang/<slug:slug>/", views.static_page, name="page"),
]
