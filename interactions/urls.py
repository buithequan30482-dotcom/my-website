from django.urls import path
from django.utils.translation import gettext_lazy as _

from . import views

app_name = "interactions"
urlpatterns = [
    path("gop-y/", views.feedback, name="feedback"),
    path("gop-y/da-gui/<str:ma>/", views.feedback_done, name="feedback_done"),
    path("tra-cuu-gop-y/", views.lookup, name="lookup"),
    path("di-tich/<slug:slug>/danh-gia/", views.review_submit, name="review_submit"),
]
