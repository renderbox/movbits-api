from django.urls import path

from . import views

urlpatterns = [
    path("verify/", views.verify_invite, name="invite_verify"),
    path("", views.invitation_list, name="invitation_list"),
    path("bulk/", views.bulk_invite, name="invitation_bulk"),
    path("<str:key>/", views.invitation_detail, name="invitation_detail"),
]
