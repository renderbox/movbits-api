from rest_framework import serializers

from shortlink.models import ReferralLink


class ReferralLinkSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="slug", read_only=True)
    title = serializers.CharField(source="name")
    url = serializers.SerializerMethodField()
    ctaText = serializers.CharField(source="cta_text", default="Learn More")
    linkType = serializers.ChoiceField(source="link_type", choices=["unique", "shared"])
    validFrom = serializers.DateField(
        source="valid_from", allow_null=True, required=False
    )
    validTo = serializers.DateField(source="valid_to", allow_null=True, required=False)
    clicks = serializers.IntegerField(source="click_count", read_only=True)
    email = serializers.EmailField(
        source="assigned_email", allow_blank=True, required=False, default=""
    )

    class Meta:
        model = ReferralLink
        fields = [
            "id",
            "title",
            "url",
            "description",
            "ctaText",
            "linkType",
            "validFrom",
            "validTo",
            "clicks",
            "enabled",
            "email",
        ]

    def get_url(self, obj):
        request = self.context.get("request")
        host = request.get_host() if request else "www.movbits.com"
        scheme = request.scheme if request else "https"
        return f"{scheme}://{host}/r/{obj.slug}"
