from django.conf import settings
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import serializers

from ..models import Episode, Season, Show, Tag, Video, VideoReceipt, Watchlist

DEFAULT_MOVBITS_POSTER_URL = "https://example.com/default-poster.png"


def _rating_from_value(value):
    if value is None:
        return 0
    return round(value / 10, 1)


class EpisodeSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="slug")
    rating = serializers.SerializerMethodField()
    chapterCount = serializers.SerializerMethodField()
    episodeNumber = serializers.IntegerField(source="order")
    poster = serializers.SerializerMethodField()
    bannerImage = serializers.SerializerMethodField()
    releaseDate = serializers.SerializerMethodField()
    isLocked = serializers.SerializerMethodField()
    showSlug = serializers.SerializerMethodField()
    showUuid = serializers.SerializerMethodField()
    seasonEpisode = serializers.SerializerMethodField()
    creatorName = serializers.SerializerMethodField()
    creatorAvatar = serializers.SerializerMethodField()

    class Meta:
        model = Episode
        fields = [
            "id",
            "title",
            "description",
            "duration",
            "rating",
            "chapterCount",
            "episodeNumber",
            "poster",
            "bannerImage",
            "releaseDate",
            "isLocked",
            "showSlug",
            "showUuid",
            "seasonEpisode",
            "creatorName",
            "creatorAvatar",
        ]

    def get_rating(self, obj):
        return _rating_from_value(obj.rating_value)

    def get_chapterCount(self, obj):
        if obj.chapter_count is None:
            return 0
        return obj.chapter_count

    def get_poster(self, obj):
        if obj.poster_url:
            return obj.poster_url
        if obj.poster_file:
            return obj.poster_file.url
        return DEFAULT_MOVBITS_POSTER_URL

    def get_bannerImage(self, obj):
        if obj.banner_url:
            return obj.banner_url
        if obj.banner_file:
            return obj.banner_file.url
        return DEFAULT_MOVBITS_POSTER_URL

    def get_releaseDate(self, obj):
        if obj.created_at:
            return obj.created_at.date().isoformat()
        return ""

    def get_isLocked(self, obj):
        return obj.playlist.filter(price__gt=0).exists()

    def get_showSlug(self, obj):
        return obj.show.slug if obj.show_id else ""

    def get_showUuid(self, obj):
        return str(obj.show.uuid) if obj.show_id else ""

    def get_seasonEpisode(self, obj):
        if obj.season:
            return f"S{obj.season.order} E{obj.order}"
        return f"E{obj.order}"

    def get_creatorName(self, obj):
        if obj.show_id and obj.show.team_id:
            return obj.show.team.name
        return ""

    def get_creatorAvatar(self, obj):
        if obj.show_id and obj.show.team_id and obj.show.team.avatar:
            return obj.show.team.avatar.url
        return ""


class VideoSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="slug")
    videoKey = serializers.CharField(source="video_key")
    isLocked = serializers.SerializerMethodField()
    poster = serializers.SerializerMethodField()
    cdn = serializers.SerializerMethodField()
    price = serializers.IntegerField()

    class Meta:
        model = Video
        fields = [
            "id",
            "title",
            "videoKey",
            "duration",
            "poster",
            "description",
            "isLocked",
            "cdn",
            "price",
        ]

    def get_isLocked(self, obj):
        # A video is locked if it has a price and the user lacks a valid receipt
        if (obj.price or 0) <= 0:
            return False

        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return True

        now = timezone.now()
        has_receipt = VideoReceipt.objects.filter(
            user=user,
            video=obj,
        ).filter(Q(expiration_date__isnull=True) | Q(expiration_date__gt=now))
        return not has_receipt.exists()

    def get_poster(self, obj):
        if obj.poster_url:
            return obj.poster_url
        return DEFAULT_MOVBITS_POSTER_URL

    def get_cdn(self, obj):
        if hasattr(obj, "get_cdn_display"):
            return obj.get_cdn_display()
        return None


class EpisodePlaylistSerializer(EpisodeSerializer):
    playlist = serializers.SerializerMethodField()

    class Meta(EpisodeSerializer.Meta):
        fields = EpisodeSerializer.Meta.fields + ["playlist"]

    def get_playlist(self, obj):
        videos = obj.playlist.all().order_by("episodevideo__order", "pk")
        return VideoSerializer(videos, many=True, context=self.context).data


class SeasonSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="slug")
    seasonNumber = serializers.IntegerField(source="order")
    episodes = serializers.SerializerMethodField()

    class Meta:
        model = Season
        fields = ["id", "title", "seasonNumber", "episodes"]

    def get_episodes(self, obj):
        episodes = Episode.objects.filter(season=obj).order_by("order")
        return EpisodeSerializer(episodes, many=True, context=self.context).data


class ShowSerializer(serializers.ModelSerializer):
    """
    Serializer for Show model

    interface Series {
        id: string;
        title: string;
        description: string;
        poster: string;
        episodes: number;
        seasons: number;
        rating: number;
        year: string;
        genre: string;
        category: string;
        isLocked: boolean;
        isNew?: boolean;
        isPopular?: boolean;
    }

    """

    id = serializers.CharField(source="slug")
    poster = serializers.SerializerMethodField()
    backdropImage = serializers.SerializerMethodField()
    bannerImage = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()
    totalEpisodes = serializers.SerializerMethodField()
    language = serializers.SerializerMethodField()
    creator = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    longDescription = serializers.SerializerMethodField()
    seasons = serializers.SerializerMethodField()

    class Meta:
        model = Show
        fields = [
            "id",
            "uuid",
            "slug",
            "title",
            "description",
            "longDescription",
            "poster",
            "backdropImage",
            "bannerImage",
            "rating",
            "year",
            "totalEpisodes",
            "language",
            "creator",
            "tags",
            "seasons",
        ]

    def get_poster(self, obj):
        if obj.poster_url:
            return obj.poster_url
        if obj.poster_file:
            return obj.poster_file.url
        return DEFAULT_MOVBITS_POSTER_URL

    def get_backdropImage(self, obj):
        if obj.banner_url:
            return obj.banner_url
        if obj.banner_file:
            return obj.banner_file.url
        # fall back to poster so the client always has something to render
        return self.get_poster(obj)

    def get_bannerImage(self, obj):
        if obj.banner_url:
            return obj.banner_url
        if obj.banner_file:
            return obj.banner_file.url
        # fall back to poster so the client always has something to render
        return self.get_poster(obj)

    def get_rating(self, obj):
        return _rating_from_value(obj.rating_value)

    def get_year(self, obj):
        if obj.created_at:
            return obj.created_at.year
        return None

    def get_totalEpisodes(self, obj):
        return Episode.objects.filter(show=obj).count()

    def get_language(self, obj):
        return "English"

    def get_creator(self, obj):
        if obj.team:
            return obj.team.name
        return "Unknown Creator"

    def get_tags(self, obj):
        tags = obj.tags.exclude(tagtype=Tag.TagType.CALL_OUT)
        return [tag.name for tag in tags]

    def get_longDescription(self, obj):
        return obj.description or ""

    def get_seasons(self, obj):
        seasons = Season.objects.filter(show=obj).order_by("order")
        serialized_seasons = SeasonSerializer(
            seasons, many=True, context=self.context
        ).data

        extras = Episode.objects.filter(show=obj, season__isnull=True).order_by("order")
        if extras.exists():
            serialized_seasons.append(
                {
                    "id": "extras",
                    "title": "Extras: More Stuff",
                    "seasonNumber": 9999,
                    "episodes": EpisodeSerializer(
                        extras, many=True, context=self.context
                    ).data,
                }
            )

        return serialized_seasons


class CreatorShowListSerializer(serializers.ModelSerializer):
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


class DiscoverShowSerializer(serializers.ModelSerializer):
    """
    Serializer for the Discover page show grid.

    Matches the Series data shape expected by DiscoverPage:
      id, title, description, poster, episodes, seasons, rating,
      year, genre, category, isLocked, isNew, isPopular

    genre and category are derived from Genre tags (TagType.GENRE).
    isNew is based on settings.NEW_SHOW_DAYS from creation date.
    isPopular is true when a tag named "Popular" is attached to the show.
    isLocked always returns False until a paywall model is implemented.
    """

    id = serializers.CharField(source="slug")
    poster = serializers.SerializerMethodField()
    episodes = serializers.SerializerMethodField()
    seasons = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()
    genre = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    isLocked = serializers.SerializerMethodField()
    isNew = serializers.SerializerMethodField()
    isPopular = serializers.SerializerMethodField()

    class Meta:
        model = Show
        fields = [
            "id",
            "title",
            "description",
            "poster",
            "episodes",
            "seasons",
            "rating",
            "year",
            "genre",
            "category",
            "isLocked",
            "isNew",
            "isPopular",
        ]

    def _genre_tag(self, obj):
        """Return the first Genre tag on the show, or None."""
        return obj.tags.filter(tagtype=Tag.TagType.GENRE).first()

    def get_poster(self, obj):
        if obj.poster_url:
            return obj.poster_url
        if obj.poster_file:
            return obj.poster_file.url
        return DEFAULT_MOVBITS_POSTER_URL

    def get_episodes(self, obj):
        return Episode.objects.filter(show=obj, active=True).count()

    def get_seasons(self, obj):
        return obj.season_set.count()

    def get_rating(self, obj):
        return _rating_from_value(obj.rating_value)

    def get_year(self, obj):
        return str(obj.created_at.year)

    def get_genre(self, obj):
        tag = self._genre_tag(obj)
        return tag.name if tag else ""

    def get_category(self, obj):
        tag = self._genre_tag(obj)
        return tag.slug if tag else "general"

    def get_isLocked(self, obj):
        # TODO: derive from a future paywall/pricing model
        return False

    def get_isNew(self, obj):
        days = getattr(settings, "NEW_SHOW_DAYS", 14)
        return (timezone.now() - obj.created_at).days <= days

    def get_isPopular(self, obj):
        return obj.tags.filter(name__iexact="Popular").exists()


class SearchResultSerializer(serializers.ModelSerializer):
    """
    Serializer for search results.

    Matches the SearchResult shape expected by SearchResultsPage:
      id, title, type, thumbnail, description, creator, rating, views,
      duration, category, tags, releaseYear, isPremium, price
    """

    id = serializers.CharField(source="slug")
    type = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()
    creator = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    views = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    releaseYear = serializers.SerializerMethodField()
    isPremium = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()

    class Meta:
        model = Show
        fields = [
            "id",
            "title",
            "type",
            "thumbnail",
            "description",
            "creator",
            "rating",
            "views",
            "duration",
            "category",
            "tags",
            "releaseYear",
            "isPremium",
            "price",
        ]

    def get_type(self, obj):
        return "show" if obj.series else "movie"

    def get_thumbnail(self, obj):
        if obj.poster_url:
            return obj.poster_url
        if obj.poster_file:
            return obj.poster_file.url
        return DEFAULT_MOVBITS_POSTER_URL

    def get_creator(self, obj):
        return obj.team.name if obj.team else ""

    def get_rating(self, obj):
        return _rating_from_value(obj.rating_value)

    def get_views(self, obj):
        return 0

    def get_duration(self, obj):
        if obj.series:
            count = Episode.objects.filter(show=obj, active=True).count()
            return f"{count} episode{'s' if count != 1 else ''}"
        return None

    def get_category(self, obj):
        tag = obj.tags.filter(tagtype=Tag.TagType.GENRE).first()
        return tag.slug if tag else "general"

    def get_tags(self, obj):
        return list(
            obj.tags.exclude(tagtype=Tag.TagType.CALL_OUT).values_list(
                "name", flat=True
            )
        )

    def get_releaseYear(self, obj):
        return obj.created_at.year if obj.created_at else None

    def get_isPremium(self, obj):
        return False

    def get_price(self, obj):
        return 0


class WatchlistItemSerializer(serializers.ModelSerializer):
    """
    Serializes a Watchlist entry into the WatchListItem shape expected by the frontend.

    interface WatchListItem {
      id: string;          // show slug
      title: string;
      poster: string;
      duration: string;    // "2h 15m" for videos, "12 episodes" for series
      rating: number;
      genre: string;
      type: 'video' | 'series';
      addedAt: string;     // relative time, e.g. "2 days ago"
      isLocked: boolean;
      description: string;
      episodes?: number;
      seasons?: number;
    }
    """

    id = serializers.SerializerMethodField()
    title = serializers.CharField(source="show.title")
    description = serializers.SerializerMethodField()
    poster = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    genre = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    addedAt = serializers.SerializerMethodField()
    isLocked = serializers.SerializerMethodField()
    episodes = serializers.SerializerMethodField()
    seasons = serializers.SerializerMethodField()

    class Meta:
        model = Watchlist
        fields = [
            "id",
            "title",
            "description",
            "poster",
            "duration",
            "rating",
            "genre",
            "type",
            "addedAt",
            "isLocked",
            "episodes",
            "seasons",
        ]

    def get_id(self, obj):
        return obj.show.slug

    def get_description(self, obj):
        return obj.show.description or ""

    def get_poster(self, obj):
        if obj.show.poster_url:
            return obj.show.poster_url
        if obj.show.poster_file:
            return obj.show.poster_file.url
        return DEFAULT_MOVBITS_POSTER_URL

    def get_rating(self, obj):
        return _rating_from_value(obj.show.rating_value)

    def get_genre(self, obj):
        tag = obj.show.tags.filter(tagtype=Tag.TagType.GENRE).first()
        return tag.name if tag else ""

    def get_type(self, obj):
        return "series" if obj.show.series else "video"

    def get_duration(self, obj):
        if obj.show.series:
            count = Episode.objects.filter(show=obj.show, active=True).count()
            return f"{count} episode{'s' if count != 1 else ''}"
        total_seconds = (
            Episode.objects.filter(show=obj.show, active=True).aggregate(
                total=Sum("duration")
            )["total"]
            or 0
        )
        hours, remainder = divmod(total_seconds, 3600)
        minutes = remainder // 60
        if hours:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def get_addedAt(self, obj):
        diff = timezone.now() - obj.created_at
        days = diff.days
        if days == 0:
            hours = diff.seconds // 3600
            if hours == 0:
                minutes = diff.seconds // 60
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        if days == 1:
            return "1 day ago"
        if days < 7:
            return f"{days} days ago"
        weeks = days // 7
        if weeks < 4:
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        months = days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"

    def get_isLocked(self, obj):
        return Video.objects.filter(
            episodevideo__playlist__show=obj.show, price__gt=0
        ).exists()

    def get_episodes(self, obj):
        if obj.show.series:
            return Episode.objects.filter(show=obj.show, active=True).count()
        return None

    def get_seasons(self, obj):
        if obj.show.series:
            return obj.show.season_set.count()
        return None
