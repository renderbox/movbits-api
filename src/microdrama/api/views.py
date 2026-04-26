from django.contrib.sites.shortcuts import get_current_site
from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from microdrama.api.serializers import (
    EpisodeAndChapterSerializer,
    SeriesDetailSerializer,
    SeriesListSerializer,
)
from microdrama.models import Chapter  # Assuming Chapter is the model for chapters
from microdrama.models import Episode  # Assuming Episode is the model for episodes
from microdrama.models import Series  # Assuming Series is the model for series data
from microdrama.models import (  # Assuming SeriesMarketing is the model for marketing data
    SeriesMarketing,
)


class BaseCatalogAPIView(APIView):
    """
    API view to fetch series data.
    """

    def get_queryset(self):
        # 1) start with the BaseCatalog queryset
        qs = Series.objects

        # 2) limit to series that have stats on *this* site
        current_site = get_current_site(self.request)
        qs = qs.filter(sites__id=current_site.id)  # , stats__site__id=current_site.id)

        # 3) bring in the likes count from the related SeriesStats
        qs = qs.annotate(site_likes=F("stats__likes"))

        # 4) order by that likes count, descending, and take the top 20
        return qs.order_by("-site_likes")[:20]

    def get(self, request):
        series = self.get_queryset()

        # Serialize the series data
        serializer = SeriesListSerializer(series, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


class TrendingSeriesAPIView(BaseCatalogAPIView):
    def get_queryset(self):
        # 1) start with the BaseCatalog queryset
        qs = Series.objects

        # 2) limit to series that have stats on *this* site
        current_site = get_current_site(self.request)
        qs = qs.filter(sites__id=current_site.id)  # , stats__site__id=current_site.id)

        # 3) bring in the likes count from the related SeriesStats
        qs = qs.annotate(site_likes=F("stats__likes"))

        # 4) order by that likes count, descending, and take the top 20
        return qs.order_by("-site_likes")[:20]


class MustSeeAPIView(BaseCatalogAPIView):
    def get_queryset(self):
        current_site = get_current_site(self.request)
        # Get SeriesMarketing for MUST_SEE placement, ordered
        qs = (
            SeriesMarketing.objects.filter(
                placement=SeriesMarketing.Placement.MUST_SEE,
                site=current_site,
            )
            .select_related("series")
            .order_by("order", "series__title")
        )
        # Return the related Series objects in order
        return Series.objects.filter(id__in=qs.values_list("series_id", flat=True))


class HiddenGemsAPIView(BaseCatalogAPIView):
    def get_queryset(self):
        current_site = get_current_site(self.request)
        # Get SeriesMarketing for HIDDEN_GEMS placement, ordered
        qs = (
            SeriesMarketing.objects.filter(
                placement=SeriesMarketing.Placement.HIDDEN_GEMS,
                site=current_site,
            )
            .select_related("series")
            .order_by("order", "series__title")
        )
        # Return the related Series objects in order
        return Series.objects.filter(id__in=qs.values_list("series_id", flat=True))


class ChapterPlaybackAPIView(APIView):
    """
    API view to fetch video playback details for a given chapter UUID.
    """

    def get(self, request, chapter_uuid):
        # Fetch the current chapter using the provided UUID
        current_chapter = get_object_or_404(Chapter, uuid=chapter_uuid)

        # Get the next chapter in the sequence, if it exists
        next_chapter = (
            current_chapter.get_next_chapter()
        )  # Assuming a method exists to fetch the next chapter

        # Prepare the response data
        response_data = {
            "video_url": current_chapter.video.url if current_chapter.video else None,
            "next_chapter_uuid": str(next_chapter.uuid) if next_chapter else None,
            "is_next_locked": next_chapter.is_locked if next_chapter else False,
        }

        return Response(response_data, status=status.HTTP_200_OK)


class EpisodeWithPlaylistAPIView(APIView):
    """
    API view to fetch the playlist of chapters for a given episode UUID.

    TODO: This will need to check the user and see which chapters are unlocked
    for that user and mark them as such in the response.
    """

    def get(self, request, episode_uuid):
        # Fetch the episode using the provided UUID
        episode = get_object_or_404(Episode, uuid=episode_uuid)

        # Serialize the episode data
        serializer = EpisodeAndChapterSerializer(episode)

        return Response(serializer.data, status=status.HTTP_200_OK)


class SeriesDetailAPIView(APIView):

    def get(self, request, team_slug, series_slug):
        # Fetch the series using the provided UUID
        series = get_object_or_404(Series, slug=series_slug, team__slug=team_slug)

        # Serialize the series data
        serializer = SeriesDetailSerializer(series)

        return Response(serializer.data, status=status.HTTP_200_OK)


class SeriesCatalogAPIView(APIView):
    """
    API view to fetch series data with links.
    """

    def get_queryset(self):
        # 1) start with the BaseCatalog queryset
        qs = Series.objects

        # 2) limit to series that have stats on *this* site
        current_site = get_current_site(self.request)
        qs = qs.filter(sites__id=current_site.id)  # , stats__site__id=current_site.id)

        # 3) bring in the likes count from the related SeriesStats
        qs = qs.annotate(site_likes=F("stats__likes"))

        # 4) order by that likes count, descending, and take the top 20
        return qs.order_by("-site_likes")[:20]

    def get(self, request):
        series = self.get_queryset()

        # Serialize the series data
        serializer = SeriesListSerializer(series, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


class VideoPlaybackAPIView(APIView):
    """
    API view to fetch video playback details for a given chapter UUID.
    """

    def get(self, request, chapter_uuid):
        # Fetch the current chapter using the provided UUID
        current_chapter = get_object_or_404(Chapter, uuid=chapter_uuid)

        # Get the next chapter in the sequence, if it exists
        # next_chapter = (
        #     current_chapter.get_next_chapter()
        # )  # Assuming a method exists to fetch the next chapter

        # Prepare the response data
        response_data = {
            "video_url": current_chapter.video.url if current_chapter.video else None,
            "status": "unlocked",  # Placeholder, actual status logic to be implemented
        }

        return Response(response_data, status=status.HTTP_200_OK)
