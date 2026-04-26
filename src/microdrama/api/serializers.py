from rest_framework import serializers

from microdrama.models import Chapter, Episode, Series


class ChapterSerializer(serializers.ModelSerializer):
    """Serializer for chapters, used in EpisodeAndChapterSerializer."""

    link = serializers.SerializerMethodField()

    class Meta:
        model = Chapter
        fields = ["uuid", "title", "chapter_number", "link"]

    def get_link(self, obj):
        return f"/player/{obj.episode.series.team.slug}/{obj.episode.series.slug}/{obj.episode.slug}/{obj.chapter_number}/"


class EpisodeAndChapterSerializer(serializers.ModelSerializer):
    """Serializer for episodes with their chapters, used in SeriesDetailSerializer."""

    chapters = ChapterSerializer(many=True, read_only=True, source="chapters.order_by")

    class Meta:
        model = Episode
        fields = ["uuid", "title", "description", "chapters"]


class EpisodeInfoSerializer(serializers.ModelSerializer):
    """Serializer for episode information, used in SeriesDetailSerializer."""

    link = serializers.SerializerMethodField()
    playerlink = serializers.SerializerMethodField()

    class Meta:
        model = Episode
        fields = ["uuid", "title", "description", "link", "order", "playerlink"]

    def get_link(self, obj):
        return f"/{obj.series.team.slug}/{obj.series.slug}/"

    def get_playerlink(self, obj):
        return f"/{obj.series.team.slug}/{obj.series.slug}/{obj.order}/player"


class SeriesDetailSerializer(serializers.ModelSerializer):
    """Serializer for series, including episodes and chapters."""

    episodes = EpisodeInfoSerializer(
        many=True, read_only=True, source="episodes.order_by"
    )

    class Meta:
        model = Series
        fields = ["title", "description", "episodes", "min_age", "poster"]


class SeriesListSerializer(serializers.ModelSerializer):
    """Serializer for listing series with basic information."""

    link = serializers.SerializerMethodField()
    creator = serializers.CharField(source="team.name", read_only=True)
    view_count = serializers.IntegerField(
        source="stats.views", read_only=True, default=0
    )
    episode_count = serializers.IntegerField(source="episodes.count", read_only=True)
    image = serializers.ImageField(source="poster", read_only=True)

    class Meta:
        model = Series
        fields = [
            "title",
            "slug",
            "image",
            "min_age",
            "creator",
            "view_count",
            "link",
            "episode_count",
        ]
        read_only_fields = ["slug", "image"]

    def get_link(self, obj):
        return f"/{obj.team.slug}/{obj.slug}/"
