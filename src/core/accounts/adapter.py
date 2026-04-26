from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings


class StoryAccountAdapter(DefaultAccountAdapter):
    """Customize email confirmation links to point to the SPA and password reset links for dj-rest-auth."""

    def get_email_confirmation_url(self, request, emailconfirmation):
        key = emailconfirmation.key
        base = (
            "http://localhost:3000"
            if getattr(settings, "DEVELOPMENT_MODE", False)
            else "https://www.movbits.com"
        )
        return f"{base}/confirm-email?key={key}"

    def send_mail(self, template_prefix, email, context):
        """
        Override to hook password reset emails when used via allauth flows.
        dj-rest-auth uses its own PasswordResetForm, so the reset URL is built via PASSWORD_RESET_CONFIRM_URL.
        """
        return super().send_mail(template_prefix, email, context)


class StorySocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Customise how SSO logins are mapped to StoryUser accounts.

    populate_user() is called by allauth after it fetches the provider profile.
    We map the common name fields so new SSO users get a proper first/last name
    rather than an empty profile.
    """

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)

        # allauth puts the full name in `data["name"]` for most providers.
        # Split it into first/last only when the provider didn't supply
        # separate fields (Google supplies both; Facebook/TikTok typically
        # only supply the full display name).
        if not user.first_name and not user.last_name:
            full_name = (data.get("name") or "").strip()
            if full_name:
                parts = full_name.split(" ", 1)
                user.first_name = parts[0]
                user.last_name = parts[1] if len(parts) > 1 else ""

        return user
