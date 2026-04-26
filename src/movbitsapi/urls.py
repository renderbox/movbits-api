from dj_rest_auth.views import PasswordResetConfirmView
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

import core.api.social_views
import core.api.views

api_v1_urls = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("schema/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("admin/", include("administration.api.urls")),
    path("series/", include("microdrama.api.urls")),
    path("maintenance/", include("maintenance.api.urls")),
    path("user/", include("core.api.urls")),
    path("analytics/", include("analytics.api.urls")),
    path("", include("analytics.api.urls_temp")),
    path("billing/", include("billing.api.urls")),
    path("viewing-history/", include("history.api.urls")),
    path("localization/", include("localization.api.urls")),
    path("shortlink/", include("shortlink.api.urls")),
    path("", include("shows.api.urls")),
    path("survey/", include("survey.api.urls")),
    path("teams/", include("team.api.urls")),
    path("support/", include("support.api.urls")),
    path("media/", include("media.api.urls")),
    path("invitations/", include("site_invitations.api.urls")),
    path("wallet/", include("wallet.api.urls")),
    path("", include("vendor.api.urls")),
    path("payment/", include("vendor.api.stripe.elements.urls")),
]

api_urls = [
    path("auth/password/reset/", core.api.views.PasswordResetView.as_view(), name="rest_password_reset"),
    path("auth/sso-providers", core.api.views.sso_providers, name="auth-sso-providers"),
    path("auth/google/", core.api.social_views.GoogleLoginView.as_view(), name="auth-google"),
    path("auth/facebook/", core.api.social_views.FacebookLoginView.as_view(), name="auth-facebook"),
    path("auth/tiktok/", core.api.social_views.TikTokLoginView.as_view(), name="auth-tiktok"),
    path("auth/instagram/", core.api.social_views.InstagramLoginView.as_view(), name="auth-instagram"),
    path("auth/google/connect/", core.api.social_views.GoogleConnectView.as_view(), name="auth-google-connect"),
    path("auth/facebook/connect/", core.api.social_views.FacebookConnectView.as_view(), name="auth-facebook-connect"),
    path("auth/tiktok/connect/", core.api.social_views.TikTokConnectView.as_view(), name="auth-tiktok-connect"),
    path("auth/instagram/connect/", core.api.social_views.InstagramConnectView.as_view(), name="auth-instagram-connect"),
    path("auth/", include("dj_rest_auth.urls")),
    path(
        "auth/password/reset/confirm/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("auth/registration/", include("core.api.registration_urls")),
    path("v1/", include(api_v1_urls)),
]

urlpatterns = [
    path("api/", include(api_urls)),
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
