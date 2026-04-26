from django.urls import path

from . import views

app_name = "shortlink_api"

urlpatterns = [
    # Specific paths must come before the generic <slug:slug>/ pattern
    path("", views.referral_links, name="referral_links"),
    path("batch/", views.batch_generate, name="batch_generate"),
    path("referral/<slug:slug>/", views.referral_lookup, name="referral_lookup"),
    path("<slug:slug>/", views.referral_link_detail, name="referral_link_detail"),
]
