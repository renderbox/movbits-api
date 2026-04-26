from django.conf import settings
from invitations.adapters import BaseInvitationsAdapter


class SiteInvitationAdapter(BaseInvitationsAdapter):
    def get_confirmation_url(self, request, invitation):
        """
        Returns the SPA signup URL for the invitation.
        Used by any non-API flows (e.g. Django admin actions) that go
        through the adapter rather than calling send_invitation() directly.
        """
        base = getattr(settings, "SPA_BASE_URL", "http://localhost:3000")
        return f"{base}/signup?invite={invitation.key}"
