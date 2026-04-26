from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class AdminUserSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    joinDate = serializers.SerializerMethodField()
    lastActive = serializers.SerializerMethodField()
    credits = serializers.SerializerMethodField()
    subscription = serializers.SerializerMethodField()
    isSuperUser = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "email",
            "username",
            "avatar",
            "role",
            "status",
            "joinDate",
            "lastActive",
            "credits",
            "subscription",
            "isSuperUser",
        ]

    def get_id(self, obj):
        return str(obj.pk)

    def get_name(self, obj):
        return obj.get_full_name() or obj.username or obj.email

    def get_avatar(self, obj):
        if obj.avatar:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return ""

    def get_role(self, obj):
        if obj.is_superuser or obj.is_staff:
            return "admin"
        return "viewer"

    def get_status(self, obj):
        return "active" if obj.is_active else "inactive"

    def get_joinDate(self, obj):
        return obj.date_joined.isoformat() if obj.date_joined else None

    def get_lastActive(self, obj):
        return obj.last_login.isoformat() if obj.last_login else None

    def get_credits(self, obj):
        # TODO: wire to wallet app — Wallet.objects.get_or_create(user=obj, ...)
        return 0

    def get_subscription(self, obj):
        # TODO: wire to billing app
        return "free"

    def get_isSuperUser(self, obj):
        return obj.is_superuser
