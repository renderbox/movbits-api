from allauth.mfa.adapter import DefaultMFAAdapter
from allauth.mfa.models import Authenticator


class MovbitsMFAAdapter(DefaultMFAAdapter):
    def is_mfa_enabled(self, user, types=None):
        if user.is_anonymous:
            return False
        # SSO-only users (no usable password) skip MFA — the identity
        # provider is already responsible for their authentication security.
        from allauth.socialaccount.models import SocialAccount
        if (
            SocialAccount.objects.filter(user=user).exists()
            and not user.has_usable_password()
        ):
            return False
        return super().is_mfa_enabled(user, types=types)

    def can_delete_authenticator(self, authenticator):
        # Superusers cannot remove their last TOTP authenticator.
        if (
            authenticator.user.is_superuser
            and authenticator.type == Authenticator.Type.TOTP
        ):
            remaining = Authenticator.objects.filter(
                user=authenticator.user,
                type=Authenticator.Type.TOTP,
            ).count()
            if remaining <= 1:
                return False
        return True
