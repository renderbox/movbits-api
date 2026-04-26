from allauth.account.views import confirm_email
from dj_rest_auth.registration.views import ResendEmailVerificationView, VerifyEmailView
from django.urls import path

from .views import RegisterView

urlpatterns = [
    path("", RegisterView.as_view(), name="rest_register"),
    path("verify-email/", VerifyEmailView.as_view(), name="rest_verify_email"),
    path(
        "resend-email/", ResendEmailVerificationView.as_view(), name="rest_resend_email"
    ),
    path(
        "account-confirm-email/<str:key>/",
        confirm_email,
        name="account_confirm_email",
    ),
]
