from django.urls import path

from . import views

urlpatterns = [
    # path("login", views.OAuth2TokenObtainPairView.as_view(), name="auth-login"),
    path("signup", views.signup, name="auth-signup"),
    path("logout", views.logout, name="auth-logout"),
    # path("refresh", views.OAuth2TokenRefreshView.as_view(), name="auth-refresh"),
    path("verify-2fa", views.verify_2fa, name="auth-verify-2fa"),
    path("password-reset", views.password_reset_request, name="auth-password-reset"),
    path(
        "auth/password-reset/confirm",
        views.password_reset_confirm,
        name="auth-password-reset-confirm",
    ),
]
