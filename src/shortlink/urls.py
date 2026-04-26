from django.urls import path

from . import views

app_name = "shortlink"

urlpatterns = [
    path("<slug:slug>/", views.referral_view, name="referral"),
]
