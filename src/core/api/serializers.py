import uuid

from dj_rest_auth.registration.serializers import (
    RegisterSerializer as RestAuthRegisterSerializer,
)
from dj_rest_auth.serializers import PasswordResetSerializer
from django.conf import settings
from django.contrib.auth import get_user_model  # , authenticate
from django.utils.text import slugify
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.settings import api_settings

from ..models import Profile

User = get_user_model()


class UserConfigSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    credits = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    isCreator = serializers.SerializerMethodField()
    isAdmin = serializers.SerializerMethodField()
    isSuperUser = serializers.SerializerMethodField()
    initials = serializers.SerializerMethodField()
    language = serializers.CharField(default="en")

    class Meta:
        model = User
        fields = [
            "credits",
            "name",
            "email",
            "username",
            "avatar",
            "isCreator",
            "isAdmin",
            "isSuperUser",
            "initials",
            "language",
        ]

    # def get_profile(self, obj):
    #     request = self.context.get("request")
    #     if hasattr(request, "profile"):
    #         return ProfileSerializer(request.profile).data
    #     return None

    def get_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_credits(self, obj):
        """Placeholder for user credits system.  Get it form the user's wallet"""
        return 10000

    def get_avatar(self, obj):
        if obj.avatar:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return ""

    def get_isCreator(self, obj):
        return True

    def get_isAdmin(self, obj):
        return obj.is_staff or obj.is_superuser

    def get_isSuperUser(self, obj):
        return obj.is_superuser

    def get_initials(self, obj):
        name = self.get_name(obj)
        initials = "".join([part[0].upper() for part in name.split() if part])
        return initials[:2]


class UserUpdateSerializer(serializers.ModelSerializer):
    firstName = serializers.CharField(
        source="first_name", required=False, allow_blank=True, default=""
    )
    lastName = serializers.CharField(
        source="last_name", required=False, allow_blank=True, default=""
    )
    username = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, default=None
    )

    class Meta:
        model = User
        fields = ("firstName", "lastName", "username")

    def validate_username(self, value):
        if not value:
            return None
        qs = User.objects.filter(username=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                _("A user with that username already exists.")
            )
        return value

    def update(self, instance, validated_data):
        instance.first_name = validated_data.get("first_name", instance.first_name)
        instance.last_name = validated_data.get("last_name", instance.last_name)
        # Allow clearing username by sending empty/None
        if "username" in validated_data:
            instance.username = validated_data.get("username") or None
        instance.save(update_fields=["first_name", "last_name", "username"])
        return instance


class RegisterSerializer(RestAuthRegisterSerializer):
    inviteKey = serializers.CharField(
        write_only=True, required=False, allow_blank=True, allow_null=True, default=None
    )
    username = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        default=None,
        write_only=True,
        validators=[],
    )
    firstName = serializers.CharField(
        write_only=True, max_length=150, required=False, allow_blank=True, default=""
    )
    lastName = serializers.CharField(
        write_only=True, max_length=150, allow_blank=True, required=False
    )
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    confirmPassword = serializers.CharField(write_only=True, trim_whitespace=False)
    agreeToTerms = serializers.BooleanField(
        write_only=True, required=True, allow_null=False
    )
    subscribeToNewsletter = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = User
        fields = (
            "email",
            "username",
            "firstName",
            "lastName",
            "password",
            "confirmPassword",
            "agreeToTerms",
            "subscribeToNewsletter",
            "inviteKey",
        )
        extra_kwargs = {
            "username": {
                "required": False,
                "allow_blank": True,
                "allow_null": True,
            }
        }

    def get_fields(self):
        fields = super().get_fields()
        # Hide base password1/password2 from the schema; we map to password/confirmPassword instead.
        fields.pop("password1", None)
        fields.pop("password2", None)
        if "firstName" in fields:
            fields["firstName"].required = False
            fields["firstName"].allow_blank = True
        if "agreeToTerms" in fields:
            fields["agreeToTerms"].required = True
            fields["agreeToTerms"].allow_null = False
        if "username" in fields:
            fields["username"].required = False
            fields["username"].allow_blank = True
            fields["username"].allow_null = True
        return fields

    def validate_username(self, value):
        if not value:
            return None
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                _("A user with that username already exists.")
            )
        return value

    def _generate_username(self, email: str, first: str, last: str) -> str:
        base = slugify(" ".join([first, last]).strip()) or slugify(email.split("@")[0])
        if not base:
            base = uuid.uuid4().hex[:8]
        candidate = base
        suffix = 1
        while User.objects.filter(username=candidate).exists():
            suffix += 1
            candidate = f"{base}-{suffix}"
        return candidate

    def validate(self, attrs):
        attrs["password1"] = attrs.get("password")
        attrs["password2"] = attrs.get("confirmPassword")
        if attrs.get("agreeToTerms") is not True:
            raise serializers.ValidationError(
                {"agreeToTerms": _("Accepting the terms is required.")}
            )
        if attrs.get("password") != attrs.get("confirmPassword"):
            raise serializers.ValidationError(
                {"confirmPassword": _("Password fields didn't match.")}
            )
        return super().validate(attrs)

    def validate_agreeToTerms(self, value):
        if value is not True:
            raise serializers.ValidationError(_("Accepting the terms is required."))
        return value

    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data.update(
            {
                "first_name": self.validated_data.get("firstName", ""),
                "last_name": self.validated_data.get("lastName", ""),
                "username": self.validated_data.get("username"),
            }
        )
        return data

    def save(self, request):
        user = super().save(request)
        if not user.username:
            user.username = self._generate_username(
                user.email, user.first_name, user.last_name
            )
            user.save(update_fields=["username"])

        subscribe_to_newsletter = self.validated_data.get(
            "subscribeToNewsletter", False
        )
        agree_to_terms = self.validated_data.get("agreeToTerms", False)
        if agree_to_terms and not user.agreed_to_terms:
            user.agreed_to_terms = True
            user.save(update_fields=["agreed_to_terms"])

        if hasattr(request, "site"):
            profile, _ = Profile.objects.get_or_create(
                user=user, site=request.site, defaults={"role": "member"}
            )
            prefs = profile.preferences or {}
            prefs.setdefault("legal", {})
            prefs["legal"]["agreeToTerms"] = bool(agree_to_terms)
            prefs["newsletter"] = {"subscribe": bool(subscribe_to_newsletter)}
            profile.preferences = prefs
            profile.save(update_fields=["preferences"])

        invite_key = self.validated_data.get("inviteKey")
        if invite_key:
            try:
                from site_invitations.models import SiteInvitation

                invitation = SiteInvitation.objects.get(
                    key=invite_key, accepted__isnull=True
                )
                if not invitation.key_expired():
                    invitation.accept()
            except Exception:
                pass

        return user


class OAuth2TokenObtainPairSerializer(TokenObtainPairSerializer):
    """OAuth2-style JWT response."""

    def validate(self, attrs):
        data = super().validate(attrs)
        return {
            "access": data["access"],
            "refresh": data["refresh"],
            "expires_in": int(api_settings.ACCESS_TOKEN_LIFETIME.total_seconds()),
            "token_type": "bearer",
        }


class OAuth2TokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        return {
            "access": data["access"],
            "expires_in": int(api_settings.ACCESS_TOKEN_LIFETIME.total_seconds()),
            "token_type": "bearer",
        }


class SPAPasswordResetSerializer(PasswordResetSerializer):
    """
    Override the reset URL to point users to the SPA.
    """

    def get_email_options(self):
        base = (
            "http://localhost:3000"
            if settings.DEVELOPMENT_MODE
            else "https://www.movbits.com"
        )

        def spa_url_generator(req, user, temp_key):
            from allauth.account.utils import user_pk_to_url_str

            uid = user_pk_to_url_str(user)
            return f"{base}/reset-password?uid={uid}&token={temp_key}"

        return {"url_generator": spa_url_generator}
