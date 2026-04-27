from django.urls import path

from . import consent_views, mfa_views, social_views, views

urlpatterns = [
    # Consent
    path("consent/items", consent_views.consent_items, name="consent-items"),
    path("consent/save", consent_views.save_consent, name="consent-save"),
    path(
        "consent/preferences",
        consent_views.get_user_consent,
        name="consent-preferences",
    ),
    path(
        "consent/update",
        consent_views.update_user_consent,
        name="consent-update",
    ),

    # 2FA / TOTP
    path("2fa/enable", mfa_views.enable_totp, name="2fa-enable"),
    path("2fa/disable", mfa_views.disable_totp, name="2fa-disable"),
    path("2fa/status", mfa_views.totp_status, name="2fa-status"),

    # Users
    path("me", views.CurrentUserView.as_view(), name="users-me"),
    path(
        "me/avatar",
        views.AvatarUploadView.as_view(),
        name="users-avatar-upload",
    ),
    path("features", views.CurrentFeaturesView.as_view(), name="users-features"),
    path("list", views.users_list, name="users-list"),
    path("profile/update", views.update_profile, name="users-update-profile"),
    path("credits", views.get_credits, name="users-credits"),
    path("devices", views.get_devices, name="users-devices"),
    path(
        "history/recent",
        views.get_history_recent,
        name="users-recent-history",
    ),
    path(
        "history/favorite",
        views.get_history_favorite,
        name="users-favorite-history",
    ),
    path("<str:user_id>/info", views.UserView.as_view(), name="users-get"),
    path("tos", views.get_tos, name="core-tos"),
    path("eula", views.get_eula, name="core-eula"),
    path("about", views.get_about, name="core-about"),
    # Social account management (requires authentication)
    path(
        "social-accounts/",
        social_views.UserSocialAccountListView.as_view(),
        name="user-social-accounts",
    ),
    path(
        "social-accounts/<int:pk>/disconnect/",
        social_views.UserSocialAccountDisconnectView.as_view(),
        name="user-social-account-disconnect",
    ),
]
