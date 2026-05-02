from datetime import date

from django.conf import settings
from django.contrib.auth.models import AbstractUser, Permission
from django.contrib.sites.models import Site
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.utils import to_lower_camel_case
from localization.models import Language


class MBUser(AbstractUser):
    username = models.CharField(
        _("username"),
        max_length=150,
        unique=True,
        null=True,
        blank=True,
        help_text=_(
            "Optional. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
        ),
        validators=[AbstractUser.username_validator],
        error_messages={"unique": _("A user with that username already exists.")},
    )
    email = models.EmailField(_("email address"), unique=True)
    date_of_birth = models.DateField(
        null=True, blank=True, help_text="Required for age-restricted content"
    )
    agreed_to_terms = models.BooleanField(
        default=False,
        help_text="Indicates if the user has agreed to the terms of service",
    )
    agreed_to_terms_date = models.DateField(
        null=True,
        blank=True,
        help_text="The date when the user agreed to the terms of service",
    )
    agreed_to_eula = models.BooleanField(
        default=False,
        help_text="Indicates if the user has agreed to the end user license agreement",
    )
    agreed_to_eula_date = models.DateField(
        null=True,
        blank=True,
        help_text="The date when the user agreed to the end user license agreement",
    )

    avatar = models.ImageField(
        upload_to="users/avatars/",
        null=True,
        blank=True,
        help_text="Profile avatar image",
    )

    stripe_customer_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        help_text="Stripe user ID for billing purposes",
    )

    preferred_language = models.ForeignKey(
        Language,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
        help_text="User's preferred display language.",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        dob = self.date_of_birth
        # basic year/month/day diff
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


class Profile(models.Model):
    user = models.ForeignKey(MBUser, on_delete=models.CASCADE, related_name="profiles")
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="profiles")
    role = models.CharField(max_length=50, default="member")
    preferences = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("user", "site")

    def __str__(self):
        return f"{self.user.email} @ {self.site.domain}"


class FeatureFlag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    key = models.CharField(max_length=100, unique=True, blank=True, null=True)
    description = models.TextField(blank=True)
    value = models.CharField(max_length=100, blank=True)
    value_type = models.CharField(
        max_length=20,
        choices=[("boolean", "Boolean"), ("string", "String"), ("number", "Number")],
        default="boolean",
    )
    is_active = models.BooleanField(default=False)
    sites = models.ManyToManyField(Site, related_name="feature_flags", blank=True)
    permissions = models.ManyToManyField(
        Permission, related_name="feature_flags", blank=True
    )

    def __str__(self):
        return f"{self.name} ({self.value_type}: {self.value})"

    def get_value(self):
        if self.value_type == "boolean":
            return self.value.lower() in ("true", "1", "yes")
        elif self.value_type == "number":
            try:
                return float(self.value)
            except ValueError:
                return None
        return self.value

    def save(self, *args, **kwargs):
        """
        This will gernerate a key for the feature flag based on the name if the key is not provided.
        The key will be a lowercase, underscore-separated version of the name, with any
        non-alphanumeric characters removed.  If the generated key already exists, a numeric suffix
        will be added to make it unique.
        """
        if not self.key:
            max_length = self._meta.get_field("key").max_length
            self.key = to_lower_camel_case(self.name, max_length=max_length)
        super().save(*args, **kwargs)


class ConsentRecord(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="consent_records",
    )
    session_key = models.CharField(max_length=40, blank=True, default="")
    preferences = models.JSONField(default=dict)
    version = models.CharField(max_length=20, default="1.0")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        identifier = (
            self.user.email if self.user_id else self.session_key or "anonymous"
        )
        return f"ConsentRecord({identifier}, v{self.version}, {self.created_at})"
