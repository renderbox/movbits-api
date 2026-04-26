from rest_framework import serializers

from ..models import Campaign, SiteInvitation


class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = ["id", "title", "created_at"]
        read_only_fields = ["id", "created_at"]


class SiteInvitationSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    campaignTitle = serializers.CharField(
        source="campaign.title", read_only=True, allow_null=True, default=None
    )

    class Meta:
        model = SiteInvitation
        fields = [
            "key",
            "email",
            "name",
            "status",
            "sent",
            "accepted",
            "campaign",
            "campaignTitle",
            "created",
        ]
        read_only_fields = ["key", "sent", "accepted", "created", "campaignTitle"]

    def get_status(self, obj):
        if obj.accepted:
            return "accepted"
        if obj.sent and obj.key_expired():
            return "expired"
        if obj.sent:
            return "pending"
        return "draft"


class SendInvitationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )


class BulkInviteSerializer(serializers.Serializer):
    campaignTitle = serializers.CharField(max_length=255)
    emails = serializers.ListField(
        child=serializers.EmailField(),
        min_length=1,
        max_length=1000,
    )
    name = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
