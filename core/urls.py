from django.urls import path

from . import admin_views, views

app_name = "core"
urlpatterns = [
    path("bao-mat/otp/", views.otp_verify, name="otp_verify"),
    path("bao-mat/bat-2-lop/", views.otp_setup, name="otp_setup"),
    path("bao-mat/tat-2-lop/", admin_views.otp_disable, name="otp_disable"),
    path("bao-mat/dat-lai-2-lop/", admin_views.otp_reset, name="otp_reset"),
    path("huong-dan/", views.help_index, name="help"),
    path("huong-dan/<slug:slug>/", views.help_detail, name="help_detail"),
]
