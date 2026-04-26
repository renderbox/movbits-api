import random

from rest_framework import serializers

from shows.models import Episode

DEFAULT_MOVBITS_POSTER_URL = (
    "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=400&h=225&fit=crop"
)


def _fake_views():
    return random.randint(10_000, 500_000)


def _fake_revenue():
    return round(random.uniform(1_000, 50_000), 2)


def _fake_engagement():
    return round(random.uniform(5.0, 10.0), 1)


class TopPerformingEpisodeSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="uuid")
    type = serializers.SerializerMethodField()
    views = serializers.SerializerMethodField()
    revenue = serializers.SerializerMethodField()
    engagement = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Episode
        fields = ("id", "title", "type", "views", "revenue", "engagement", "thumbnail")

    def get_type(self, obj):
        return "episode"

    def get_views(self, obj):
        # TODO: replace with real view count from analytics model
        return _fake_views()

    def get_revenue(self, obj):
        # TODO: replace with real revenue from billing receipts
        return _fake_revenue()

    def get_engagement(self, obj):
        # TODO: replace with real engagement score from analytics model
        return _fake_engagement()

    def get_thumbnail(self, obj):
        if obj.poster_url:
            return obj.poster_url
        if obj.poster_file:
            return obj.poster_file.url
        return DEFAULT_MOVBITS_POSTER_URL
