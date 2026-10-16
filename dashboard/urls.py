from django.urls import path

from . import views

app_name = "dashboard"
urlpatterns = [
    path("", views.index, name="index"),
    path("kiem-duyet/", views.moderation, name="moderation"),
    path("kiem-duyet/thao-tac/", views.moderation_action, name="moderation_action"),
    path("xuat-excel/", views.export_xlsx, name="export_xlsx"),
    path("xuat-csv/", views.export_csv, name="export_csv"),
]
