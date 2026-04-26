import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone
from invitations.adapters import get_invitations_adapter
from invitations.base_invitation import AbstractBaseInvitation
from invitations.signals import invite_accepted, invite_url_sent

from .utils import generate_invite_key


class Campaign(models.Model):
    title = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitation_campaigns",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class SiteInvitation(AbstractBaseInvitation):
    # AbstractBaseInvitation (2.x) provides only `inviter` and `sent`.
    # All other fields must be defined on the concrete model.
    email = models.EmailField(max_length=254)
    key = models.CharField(max_length=64, unique=True, default=generate_invite_key)
    created = models.DateTimeField(auto_now_add=True)
    # Override the abstract base's BooleanField with a DateTimeField so we
    # can record exactly when the invite was accepted.
    accepted = models.DateTimeField(null=True, blank=True)
    name = models.CharField(max_length=255, blank=True)
    campaign = models.ForeignKey(
        Campaign,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invitations",
    )

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"Invite: {self.email}"

    def key_expired(self):
        if not self.sent:
            return False
        expiry_days = getattr(settings, "INVITATIONS_INVITATION_EXPIRY", 7)
        return self.sent + datetime.timedelta(days=expiry_days) <= timezone.now()

    def send_invitation(self, request, **kwargs):
        """
        Send the invitation email and stamp `sent` with the current time.

        Builds the SPA signup URL directly from SPA_BASE_URL rather than
        using Django's reverse(), since the confirmation route lives in the
        React app, not in Django's URL conf.
        """
        spa_base = getattr(settings, "SPA_BASE_URL", "http://localhost:3000")
        invite_url = f"{spa_base}/signup?invite={self.key}"

        context = {
            "invite_url": invite_url,
            "email": self.email,
            "key": self.key,
            "inviter": self.inviter,
            "name": self.name,
            "expiry_days": getattr(settings, "INVITATIONS_INVITATION_EXPIRY", 7),
        }

        get_invitations_adapter().send_mail(
            "invitations/email/email_invite",
            self.email,
            context,
        )

        self.sent = timezone.now()
        self.save(update_fields=["sent"])

        invite_url_sent.send(
            sender=self.__class__,
            instance=self,
            invite_url_sent=invite_url,
            inviter=self.inviter,
        )

    def accept(self):
        self.accepted = timezone.now()
        self.save(update_fields=["accepted"])
        invite_accepted.send(sender=self.__class__, email=self.email, invitation=self)
