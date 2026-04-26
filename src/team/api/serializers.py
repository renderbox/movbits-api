from rest_framework import serializers

from shows.api.serializers import DEFAULT_MOVBITS_POSTER_URL
from shows.models import Show

from ..models import Team, TeamMembership


class TeamDetailSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()


class TeamMemberSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    joinedDate = serializers.DateTimeField(source="created_at")
    lastActive = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = TeamMembership
        fields = (
            "id",
            "name",
            "email",
            "avatar",
            "role",
            "joinedDate",
            "lastActive",
            "status",
        )

    def get_id(self, obj):
        return str(obj.user.id)

    def get_name(self, obj):
        return obj.user.get_full_name() or obj.user.email

    def get_email(self, obj):
        return obj.user.email

    def get_avatar(self, obj):
        if obj.user.avatar:
            request = self.context.get("request")
            url = obj.user.avatar.url
            return request.build_absolute_uri(url) if request else url
        return None

    def get_role(self, obj):
        return TeamMembership.Role(obj.role).label.lower()

    def get_lastActive(self, obj):
        # TODO: replace with real last-activity tracking
        last_login = obj.user.last_login
        if last_login:
            return last_login.isoformat()
        return None

    def get_status(self, obj):
        if not obj.active:
            return "inactive"
        return "active"


class TeamListSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="uuid", read_only=True)
    role = serializers.SerializerMethodField()
    memberCount = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ("id", "slug", "name", "avatar", "role", "memberCount", "verified")

    def get_role(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if not user or not user.is_authenticated:
            return "member"

        if not hasattr(self, "_role_by_team_id"):
            parent_instance = getattr(self.parent, "instance", None)
            if parent_instance is None:
                team_ids = [obj.id]
            else:
                team_ids = [team.id for team in parent_instance]

            memberships = TeamMembership.objects.filter(
                user=user,
                team_id__in=team_ids,
            ).values_list("team_id", "role")

            self._role_by_team_id = {}
            for team_id, role in memberships:
                try:
                    self._role_by_team_id[team_id] = TeamMembership.Role(
                        role
                    ).label.lower()
                except (ValueError, AttributeError):
                    self._role_by_team_id[team_id] = "member"

        return self._role_by_team_id.get(obj.id) or "member"

    def get_memberCount(self, obj):
        return obj.members.count()

    # Avatar URL with 100x100 size, should return a default avatar if no avatar is set
    def get_avatar(self, obj):
        if obj.avatar:
            return obj.avatar.url + "?w=100&h=100&fit=crop&crop=face"
        else:
            return "https://images.unsplash.com/photo-1560472354-b33ff0c44a43?w=100&h=100&fit=crop&crop=face"


class TeamShowListSerializer(serializers.ModelSerializer):
    """
    Serializer for the Creator Dashboard show list.

    Matches the ContentItem shape expected by the SPA:
      id, title, type, visibility, views, watchTime, revenue,
      lastUpdated, thumbnail, status

    Fields that don't yet exist on the model (views, watchTime, revenue,
    visibility, status) return baked mock values and are marked TODO so
    they're easy to find when we wire up real data.
    """

    id = serializers.CharField(source="uuid")
    type = serializers.SerializerMethodField()
    visibility = serializers.SerializerMethodField()
    views = serializers.SerializerMethodField()
    watchTime = serializers.SerializerMethodField()
    revenue = serializers.SerializerMethodField()
    lastUpdated = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Show
        fields = [
            "id",
            "title",
            "type",
            "visibility",
            "views",
            "watchTime",
            "revenue",
            "lastUpdated",
            "thumbnail",
            "status",
        ]

    def get_type(self, obj):
        # TODO: derive from a future content_type field on Show
        return "show"

    def get_visibility(self, obj):
        # TODO: derive from a future visibility field on Show
        return "public"

    def get_views(self, obj):
        # TODO: aggregate from analytics when the analytics model is wired up
        return 0

    def get_watchTime(self, obj):
        # TODO: aggregate from analytics when the analytics model is wired up
        return 0

    def get_revenue(self, obj):
        # TODO: aggregate from billing receipts when available
        return 0

    def get_lastUpdated(self, obj):
        # Return ISO 8601 timestamp; the client formats it for display
        return obj.updated_at.isoformat()

    def get_thumbnail(self, obj):
        if obj.poster_url:
            return obj.poster_url
        if obj.poster_file:
            return obj.poster_file.url
        return DEFAULT_MOVBITS_POSTER_URL

    def get_status(self, obj):
        # TODO: derive from a future status/workflow field on Show
        # For now: active shows are published, inactive are draft
        return "published" if obj.active else "draft"
