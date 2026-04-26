from django.urls import path

from .views import movbits_redirect

app_name = "core"

urlpatterns = [
    path("", movbits_redirect, name="home"),
]
