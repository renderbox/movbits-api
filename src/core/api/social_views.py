"""
SSO login views — one per provider.

Each view accepts a POST with either:
  { "access_token": "<provider-issued token>" }
or the authorization-code exchange flow:
  { "code": "<OAuth code>", "redirect_uri": "<SPA callback URL>" }

On success the response matches the standard dj-rest-auth login shape:
  { "access": "<JWT>", "refresh": "<JWT>", "user": { ... } }

The redirect_uri sent by the frontend must exactly match the OAuth app's
registered callback URL and the SPA_BASE_URL-derived value below.
"""

from allauth.socialaccount.providers.facebook.views import FacebookOAuth2Adapter
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.instagram.views import InstagramOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from allauth.socialaccount.providers.tiktok.views import TikTokOAuth2Adapter
from dj_rest_auth.registration.views import (
    SocialAccountDisconnectView,
    SocialAccountListView,
    SocialConnectView,
    SocialLoginView,
)
from django.conf import settings


def _callback_url() -> str:
    """SPA OAuth callback URL — must match the registered redirect URI in each provider's OAuth app."""
    base = getattr(settings, "SPA_BASE_URL", "http://localhost:3000").rstrip("/")
    return f"{base}/auth/callback"


class GoogleLoginView(SocialLoginView):
    """Exchange a Google OAuth2 code for Movbits JWT tokens."""

    adapter_class = GoogleOAuth2Adapter
    client_class = OAuth2Client

    @property
    def callback_url(self):
        return _callback_url()


class FacebookLoginView(SocialLoginView):
    """Exchange a Facebook OAuth2 code for Movbits JWT tokens."""

    adapter_class = FacebookOAuth2Adapter
    client_class = OAuth2Client

    @property
    def callback_url(self):
        return _callback_url()


class TikTokLoginView(SocialLoginView):
    """Exchange a TikTok OAuth2 code for Movbits JWT tokens."""

    adapter_class = TikTokOAuth2Adapter
    client_class = OAuth2Client

    @property
    def callback_url(self):
        return _callback_url()


class InstagramLoginView(SocialLoginView):
    """
    Exchange an Instagram OAuth2 code for Movbits JWT tokens.

    NOTE: Instagram Basic Display API was deprecated January 2025.
    This view only works with Meta apps approved before the cutoff.
    New integrations should use Facebook Login with Instagram permissions instead.
    """

    adapter_class = InstagramOAuth2Adapter
    client_class = OAuth2Client

    @property
    def callback_url(self):
        return _callback_url()


# ── Account linking (connect / disconnect) ────────────────────────────────────
# These endpoints require an authenticated user (valid JWT in Authorization header).
# Connect: same OAuth flow as login, but attaches the new provider to the
#          existing account instead of issuing new tokens.
# Disconnect: removes a linked social account by its SocialAccount PK.
#             allauth validates that the user won't be locked out before deleting.


class GoogleConnectView(SocialConnectView):
    adapter_class = GoogleOAuth2Adapter
    client_class = OAuth2Client

    @property
    def callback_url(self):
        return _callback_url()


class FacebookConnectView(SocialConnectView):
    adapter_class = FacebookOAuth2Adapter
    client_class = OAuth2Client

    @property
    def callback_url(self):
        return _callback_url()


class TikTokConnectView(SocialConnectView):
    adapter_class = TikTokOAuth2Adapter
    client_class = OAuth2Client

    @property
    def callback_url(self):
        return _callback_url()


class InstagramConnectView(SocialConnectView):
    adapter_class = InstagramOAuth2Adapter
    client_class = OAuth2Client

    @property
    def callback_url(self):
        return _callback_url()


# Re-export the dj-rest-auth generic views so urls.py only imports from here.
UserSocialAccountListView = SocialAccountListView
UserSocialAccountDisconnectView = SocialAccountDisconnectView
