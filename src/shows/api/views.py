import datetime
import random
import uuid

from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from events.emit import TOPIC_ENGAGEMENT, TOPIC_REVENUE, emit
from events.schemas import ChapterUnlockedEvent, VideoRatingEvent, WatchlistEvent
from shows import mock_data
from wallet.models import CreditTypes, Wallet, WalletTransaction

from ..models import (
    Episode,
    RevShareDeal,
    Show,
    Tag,
    Video,
    VideoRating,
    VideoReceipt,
    Watchlist,
)
from .serializers import (  # EpisodeSerializer,
    CreatorShowListSerializer,
    DiscoverShowSerializer,
    EpisodePlaylistSerializer,
    SearchResultSerializer,
    ShowSerializer,
    VideoSerializer,
    WatchlistItemSerializer,
)

# ── CloudFront signed cookie helper ───────────────────────────────────────────


def _generate_cf_signed_cookies(
    key_pair_id: str, private_key_pem: str, resource: str, expires_at
) -> dict:
    """
    Return the three CloudFront signed cookie values for a custom policy.

    `resource` may contain a wildcard, e.g.
      https://cdn.example.com/videos/{uuid}/hls/*
    which grants access to every file under that path until `expires_at`.
    """
    import base64
    import json

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding as crypto_padding

    policy = json.dumps(
        {
            "Statement": [
                {
                    "Resource": resource,
                    "Condition": {
                        "DateLessThan": {"AWS:EpochTime": int(expires_at.timestamp())}
                    },
                }
            ]
        },
        separators=(",", ":"),
    )

    def _cf_b64(data: bytes) -> str:
        return (
            base64.b64encode(data)
            .decode()
            .replace("+", "-")
            .replace("=", "_")
            .replace("/", "~")
        )

    pem = (
        private_key_pem.encode()
        if isinstance(private_key_pem, str)
        else private_key_pem
    )
    private_key = serialization.load_pem_private_key(pem, password=None)
    signature = private_key.sign(
        policy.encode(), crypto_padding.PKCS1v15(), hashes.SHA1()
    )

    return {
        "CloudFront-Policy": _cf_b64(policy.encode()),
        "CloudFront-Signature": _cf_b64(signature),
        "CloudFront-Key-Pair-Id": key_pair_id,
    }


# from unittest import mock

# Updated Show structure
# team->show->season/episode->playlist/chapters
# SHOW ID: <team>_<show>_<season/episode>_<chapter>_<?resolution>
# star-wars_clone-wars_s01e10-03    # episodics have seasons
# star-wars_empire-strikes-back_e05-03  # Movies do not have seasons (season = 0)


# --------- Mock helpers -----------------------------------------------------
def now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"


def make_show(
    idx=1, content_type="movie", title=None, creator="Creator", premium=False
):
    sid = str(uuid.uuid4())
    return {
        "id": sid,
        "title": title or f"Sample Show {idx}",
        "description": f"Description for show {idx}",
        "thumbnail": f"https://picsum.photos/seed/{sid}/400/225",
        "contentType": content_type,
        "visibility": "public",
        "status": "published",
        "views": random.randint(0, 10000),
        "watchTime": random.randint(0, 100000),
        "revenue": round(random.random() * 1000, 2),
        "rating": round(random.uniform(1, 5), 1),
        "duration": random.randint(10, 180),
        "releaseDate": now_iso(),
        "lastUpdated": now_iso(),
        "creator": creator,
        "creatorId": str(uuid.uuid4()),
        "tags": ["drama", "example"],
        "category": "Entertainment",
        "isPremium": premium,
        "price": 1.99 if premium else 0.0,
        "parentId": None,
    }


def make_episode(idx=1, series_id=None, series_name="Sample Series"):
    eid = str(uuid.uuid4())
    return {
        "id": eid,
        "seriesId": series_id or str(uuid.uuid4()),
        "seriesName": series_name,
        "franchiseId": None,
        "franchiseName": None,
        "title": f"Episode {idx}",
        "description": f"Episode {idx} description",
        "thumbnail": f"https://picsum.photos/seed/{eid}/400/225",
        "episodeNumber": idx,
        "duration": random.randint(10, 60),
        "views": random.randint(0, 10000),
        "releaseDate": now_iso(),
    }


def make_series(idx=1, franchise_id=None, franchise_name=None):
    sid = str(uuid.uuid4())
    return {
        "id": sid,
        "franchiseId": franchise_id,
        "franchiseName": franchise_name,
        "name": f"Series {idx}",
        "description": f"Series {idx} description",
        "thumbnail": f"https://picsum.photos/seed/{sid}/400/225",
        "episodeCount": random.randint(1, 20),
        "totalViews": random.randint(0, 100000),
        "createdAt": now_iso(),
    }


def make_franchise(idx=1):
    fid = str(uuid.uuid4())
    return {
        "id": fid,
        "name": f"Franchise {idx}",
        "description": f"Franchise {idx} description",
        "thumbnail": f"https://picsum.photos/seed/{fid}/400/225",
        "seriesCount": random.randint(1, 10),
        "totalEpisodes": random.randint(5, 100),
        "totalViews": random.randint(1000, 100000),
        "createdAt": now_iso(),
    }


# --------- Shows endpoints -------------------------------------------------


class ShowListView(APIView):
    """
    GET /shows?team_id=<uuid>

    Returns the list of shows belonging to the specified team.
    The authenticated user must be a member of that team.

    Query params:
      team_id (required) — UUID of the team whose shows to return
    """

    # permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        team_id = request.query_params.get("team_id")
        if not team_id:
            return Response(
                {"detail": "team_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shows = (
            Show.objects.filter(
                team__uuid=team_id,
                team__members=request.user,
            )
            .select_related("team")
            .order_by("-updated_at")
        )

        serializer = CreatorShowListSerializer(shows, many=True)
        return Response(serializer.data)


@api_view(["GET", "PUT", "DELETE"])
def show_detail(request, show_id):
    if request.method == "GET":
        return Response(make_show(title=f"Show {show_id}"))
    if request.method == "PUT":
        data = request.data or {}
        show = make_show(title=f"Show {show_id}")
        show.update(data)
        return Response(show)
    if request.method == "DELETE":
        return Response({"success": True})


@api_view(["POST"])
def create_show(request):
    data = request.data or {}
    show = make_show(title=data.get("title", "New Show"))
    show.update(data)
    return Response(show, status=status.HTTP_201_CREATED)


_PLAYBACK_EVENT_TYPES = {
    "chapter.started",
    "chapter.paused",
    "chapter.resumed",
    "chapter.completed",
    "chapter.abandoned",
    "chapter.seeked",
    "chapter.stalled",
    "chapter.replayed",
}


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def chapter_playback_event(request):
    """
    POST /chapter/playback-event

    Records a chapter-level playback lifecycle event and emits it to the
    analytics Pub/Sub topic.  Authentication is required so we can attach a
    user_id; unauthenticated playback is not supported.

    Request body (JSON):
      event_type        required  one of: chapter.started | chapter.completed |
                                          chapter.abandoned | chapter.seeked |
                                          chapter.stalled   | chapter.replayed
      video_id          required  Video slug
      session_id        required  opaque client session identifier
      position_seconds  required  current playback position (integer)
      duration_seconds  optional  full chapter duration in seconds
      percent_complete  optional  float 0–100
      device_type       optional  mobile | desktop | tablet | tv
      seek_from_seconds optional  chapter.seeked only
      seek_to_seconds   optional  chapter.seeked only
      stall_duration_ms optional  chapter.stalled only

    Returns 202 Accepted on success.  The event is fire-and-forget; failures
    in the emission layer do not propagate to the client.
    """
    from events.emit import TOPIC_ANALYTICS
    from events.schemas import ChapterPlaybackEvent

    data = request.data

    event_type = data.get("event_type", "")
    if event_type not in _PLAYBACK_EVENT_TYPES:
        return Response(
            {
                "detail": f"Invalid event_type. Must be one of: {sorted(_PLAYBACK_EVENT_TYPES)}"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    video_id = data.get("video_id", "")
    if not video_id:
        return Response(
            {"detail": "video_id is required."}, status=status.HTTP_400_BAD_REQUEST
        )

    session_id = data.get("session_id", "")
    if not session_id:
        return Response(
            {"detail": "session_id is required."}, status=status.HTTP_400_BAD_REQUEST
        )

    # Resolve episode/show context from the video — best-effort, non-fatal if missing
    video_uuid = ""
    episode_id = ""
    show_id = ""
    creator_team_id = ""
    duration_seconds = int(data.get("duration_seconds", 0))

    try:
        video = Video.objects.get(slug=video_id)
        video_uuid = str(video.uuid)
        if not duration_seconds:
            duration_seconds = video.duration or 0
        episode = (
            Episode.objects.select_related("show__team")
            .filter(playlist=video)
            .order_by("episodevideo__order", "pk")
            .first()
        )
        if episode:
            episode_id = str(episode.uuid)
            if episode.show_id:
                show_id = str(episode.show.uuid)
                if episode.show.team_id:
                    creator_team_id = str(episode.show.team.uuid)
    except Video.DoesNotExist:
        pass  # emit the event anyway with the ids we have

    # On first play of a purchased video, start the access window.
    if event_type == "chapter.started":
        window_hours = getattr(settings, "VIDEO_ACCESS_WINDOW_HOURS", 24)
        now = timezone.now()
        VideoReceipt.objects.filter(
            user=request.user,
            video__slug=video_id,
            watch_started_at__isnull=True,
        ).update(
            watch_started_at=now,
            expiration_date=now + timezone.timedelta(hours=window_hours),
        )

    emit(
        TOPIC_ANALYTICS,
        ChapterPlaybackEvent(
            event_type=event_type,
            video_id=video_uuid
            or video_id,  # prefer UUID; fall back to slug if video not found
            episode_id=episode_id,
            show_id=show_id,
            creator_team_id=creator_team_id,
            user_id=str(request.user.pk),
            session_id=session_id,
            position_seconds=int(data.get("position_seconds", 0)),
            duration_seconds=duration_seconds,
            percent_complete=float(data.get("percent_complete", 0.0)),
            device_type=data.get("device_type", ""),
            seek_from_seconds=data.get("seek_from_seconds"),
            seek_to_seconds=data.get("seek_to_seconds"),
            stall_duration_ms=data.get("stall_duration_ms"),
            ip_address=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        ),
    )

    return Response(status=status.HTTP_202_ACCEPTED)


@api_view(["GET"])
def shows_genres(request):
    """
    GET /shows/genres

    Returns Genre tags that have at least one active show attached.
    Used by the Discover page to populate category tabs.
    """
    tags = (
        Tag.objects.filter(tagtype=Tag.TagType.GENRE, show__active=True)
        .distinct()
        .order_by("name")
    )
    data = [{"id": tag.slug, "label": tag.name} for tag in tags]
    return Response(data)


@api_view(["GET"])
def shows_discover(request):
    """
    GET /shows/discover

    Returns all active shows serialized for the Discover page.
    The frontend filters and groups by category/isPopular locally.
    """
    shows = (
        Show.objects.filter(active=True)
        .prefetch_related("tags", "season_set", "episode_set")
        .order_by("-created_at")
    )
    serializer = DiscoverShowSerializer(shows, many=True, context={"request": request})
    return Response(serializer.data)


@api_view(["GET"])
def shows_category(request, category):
    # get the parameter from the URL
    # category = request.query_params.get("category", "featured")
    limit = int(request.query_params.get("limit", 10))

    if category == "featured":
        items = mock_data.FEATURED_SHOWS[:limit]
    elif category == "trending":
        items = mock_data.TRENDING_SHOWS[:limit]
    elif category == "must_see":
        items = mock_data.MUST_SEE_SHOWS[:limit]
    elif category == "hidden_gems":
        items = mock_data.HIDDEN_GEMS_SHOWS[:limit]
    else:
        items = mock_data.RECOMMENDED_SHOWS[:limit]

    return Response(items)


@api_view(["GET"])
def shows_featured(request):
    limit = int(request.query_params.get("limit", 10))
    items = mock_data.FEATURED_SHOWS[:limit]
    return Response(items)


@api_view(["GET"])
def shows_trending(request):
    # Update this to use the serializers and real data
    limit = int(request.query_params.get("limit", 10))
    items = mock_data.TRENDING_SHOWS[:limit]
    return Response(items)


@api_view(["GET"])
def shows_must_see(request):
    limit = int(request.query_params.get("limit", 10))
    items = mock_data.MUST_SEE_SHOWS[:limit]
    return Response(items)


@api_view(["POST"])
def shows_by_category(request):
    """
    Here is a sample response for a show.

    {
      id: 'video-1',  # uuid?
      # slug: 'video-1',
      title: 'Big Buck Bunny - Animated Short Film',
      description: 'A charming animated short film about a giant rabbit who defends a trio of defenseless rodents against two bullying rodents.',
      thumbnail: 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=800&h=450&fit=crop',
      contentType: 'movie',
      visibility: 'public',
      status: 'published',
      views: 25000,
      watchTime: 14900,
      revenue: 1500.00,
      rating: 4.7,
      duration: 596,
      releaseDate: '2024-10-01',
      lastUpdated: '2024-10-29',
      creator: 'Blender Foundation', # Team Name
      creatorId: 'user-2', # Team ID
      tags: ['Animation', 'Short Film', 'Family'],
      category: 'Movies',
      isPremium: false,
    },
    """
    # TODO: Category needs to come from the URL parameters
    payload = request.data or {}
    category = payload.get("category", "General")
    items = [make_show(i, title=f"{category} Show {i}") for i in range(1, 6)]
    return Response(items)


@api_view(["GET"])
def shows_search(request):
    q = request.query_params.get("q", "").strip()
    qs = (
        Show.objects.filter(active=True).select_related("team").prefetch_related("tags")
    )
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(tags__name__icontains=q)
        ).distinct()
    serializer = SearchResultSerializer(qs[:50], many=True)
    return Response(serializer.data)


# --------- Franchise endpoints ---------------------------------------------


@api_view(["GET", "POST"])
def franchises_list(request):
    if request.method == "GET":
        items = [make_franchise(i) for i in range(1, 6)]
        return Response(items)
    data = request.data or {}
    f = make_franchise()
    f.update(data)
    return Response(f, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
def franchise_detail(request, franchise_id):
    if request.method == "GET":
        return Response(make_franchise())
    if request.method == "PUT":
        data = request.data or {}
        f = make_franchise()
        f.update(data)
        return Response(f)
    return Response({"success": True})


@api_view(["GET"])
def franchise_series(request, franchise_id):
    items = [
        make_series(
            i, franchise_id=franchise_id, franchise_name=f"Franchise {franchise_id}"
        )
        for i in range(1, 6)
    ]
    return Response(items)


# --------- Series endpoints ------------------------------------------------


@api_view(["GET", "POST"])
def series_list(request):
    if request.method == "GET":
        items = [make_series(i) for i in range(1, 11)]
        return Response(items)
    data = request.data or {}
    s = make_series()
    s.update(data)
    return Response(s, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
def series_detail(request, series_id):
    if request.method == "GET":
        return Response(make_series())
    if request.method == "PUT":
        data = request.data or {}
        s = make_series()
        s.update(data)
        return Response(s)
    return Response({"success": True})


@api_view(["GET"])
def series_episodes(request, series_id):
    items = [
        make_episode(i, series_id=series_id, series_name=f"Series {series_id}")
        for i in range(1, 9)
    ]
    return Response(items)


# --------- Episodes endpoints ----------------------------------------------


@api_view(["GET", "POST"])
def episodes_list(request):
    if request.method == "GET":
        items = [make_episode(i) for i in range(1, 21)]
        return Response(items)
    data = request.data or {}
    e = make_episode(1)
    e.update(data)
    return Response(e, status=status.HTTP_201_CREATED)


# @api_view(["GET", "PUT", "DELETE"])
# def episode_detail(request, episode_id):
#     if request.method == "GET":
#         return Response(make_episode(1))
#     if request.method == "PUT":
#         data = request.data or {}
#         e = make_episode(1)
#         e.update(data)
#         return Response(e)
#     return Response({"success": True})


# --------- Watchlist endpoints ---------------------------------------------


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def watchlist_get(request):
    items = (
        Watchlist.objects.filter(user=request.user)
        .select_related("show")
        .prefetch_related("show__tags")
        .order_by("-created_at")
    )
    return Response(
        WatchlistItemSerializer(items, many=True, context={"request": request}).data
    )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def watchlist_add(request):
    show_id = request.data.get("showId")
    show = get_object_or_404(Show, slug=show_id, active=True)
    _, created = Watchlist.objects.get_or_create(user=request.user, show=show)
    if created:
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[
            0
        ].strip() or request.META.get("REMOTE_ADDR", "")
        emit(
            TOPIC_ENGAGEMENT,
            WatchlistEvent(
                event_type="watchlist.added",
                user_id=str(request.user.pk),
                show_id=str(show.uuid),
                source=request.data.get("source", ""),
                session_id=request.META.get("HTTP_X_SESSION_ID", ""),
                ip_address=ip,
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            ),
        )
    return Response({"success": True})


@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated])
def watchlist_remove(request):
    show_slug = request.data.get("showId")
    # Capture the UUID before deletion — after .delete() the row is gone.
    show_uuid = (
        Show.objects.filter(slug=show_slug).values_list("uuid", flat=True).first()
    )
    deleted_count, _ = Watchlist.objects.filter(
        user=request.user, show__slug=show_slug
    ).delete()
    if deleted_count and show_uuid:
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[
            0
        ].strip() or request.META.get("REMOTE_ADDR", "")
        emit(
            TOPIC_ENGAGEMENT,
            WatchlistEvent(
                event_type="watchlist.removed",
                user_id=str(request.user.pk),
                show_id=str(show_uuid),
                source=request.data.get("source", ""),
                session_id=request.META.get("HTTP_X_SESSION_ID", ""),
                ip_address=ip,
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            ),
        )
    return Response({"success": True})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def watchlist_check(request, show_id):
    in_watchlist = Watchlist.objects.filter(
        user=request.user, show__slug=show_id
    ).exists()
    return Response({"inWatchlist": in_watchlist})


# --------- Playback endpoints ---------------------------------------------


@api_view(["GET"])
def playback_next(request):
    current_video_id = request.query_params.get("currentVideoId")  # noqa: F841
    playlist_id = request.query_params.get("playlistId")  # noqa: F841

    # Simple mock: sometimes return locked response to emulate paywall
    if random.random() < 0.15:
        locked = {
            "id": str(uuid.uuid4()),
            "title": "Locked Video Demo",
            "backdropImage": f"https://picsum.photos/seed/{random.randint(1, 9999)}/1200/600",
            "poster": f"https://picsum.photos/seed/{random.randint(1, 9999)}/400/225",
            "duration": 120,
            "description": "This video is locked. Unlock options provided.",
            "unlockOptions": {
                "creditsAvailable": True,
                "creditsCost": 10,
                "advertisementAvailable": True,
            },
        }
        return Response(locked, status=402)

    next_video = {
        "id": str(uuid.uuid4()),
        "title": "Next Demo Video",
        "url": None,
        "youtubeId": "dQw4w9WgXcQ",
        "poster": f"https://picsum.photos/seed/{random.randint(1, 9999)}/400/225",
        "duration": 360,
        "description": "Automatically selected next video.",
    }
    return Response(next_video)


class EpisodeDetailView(APIView):
    def _get_episode(self, episode_id):
        filters = Q(slug=episode_id)
        try:
            filters |= Q(uuid=uuid.UUID(episode_id))
        except ValueError:
            pass
        return get_object_or_404(Episode, filters)

    def get(self, request, episode_id):
        episode = self._get_episode(episode_id)
        episode = Episode.objects.select_related("show__team", "season").get(
            pk=episode.pk
        )
        serializer = EpisodePlaylistSerializer(episode, context={"request": request})
        return Response(serializer.data)


class VideoDetailView(APIView):
    def _get_video(self, video_id):
        filters = Q(slug=video_id)
        try:
            filters |= Q(uuid=uuid.UUID(video_id))
        except ValueError:
            pass
        return get_object_or_404(Video, filters)

    def get(self, request, video_id):
        video = self._get_video(video_id)  # prefetch_related VideoReciept?
        serializer = VideoSerializer(video, context={"request": request})
        return Response(serializer.data)


# add authntication check


class VideoURLView(APIView):
    """Returns a series of responses based on video lock status, user authentication and if the user has purchased the video."""

    def _get_video(self, video_id):
        filters = Q(slug=video_id)
        try:
            filters |= Q(uuid=uuid.UUID(video_id))
        except ValueError:
            pass
        return get_object_or_404(Video, filters)

    def _user_has_receipt(self, user, video):
        now = timezone.now()
        return (
            VideoReceipt.objects.filter(user=user, video=video)
            .filter(Q(expiration_date__isnull=True) | Q(expiration_date__gt=now))
            .exists()
        )

    def _build_video_payload(self, video):
        key = video.video_key or video.uuid
        cdn_map = {
            Video.CDNChoices.VIMEO: "vimeo",
            Video.CDNChoices.YOUTUBE: "youtube",
            Video.CDNChoices.S3_MEDIA_BUCKET: "s3",
        }
        cdn = cdn_map.get(video.cdn, "movbits")

        if video.cdn == Video.CDNChoices.YOUTUBE:
            url = f"https://www.youtube.com/watch?v={key}"
        elif video.cdn == Video.CDNChoices.VIMEO:
            url = f"https://player.vimeo.com/video/{key}"
        else:
            url = self.request.build_absolute_uri(
                reverse("hls_playlist", kwargs={"video_id": str(video.uuid)})
            )

        return {"videoUrl": url, "cdn": cdn}

    def get(self, request, video_id):
        video = self._get_video(video_id)
        is_paid = (video.price or 0) > 0

        if is_paid:
            if not request.user.is_authenticated:
                return Response(
                    {"detail": "Authentication required."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            if self._user_has_receipt(request.user, video):
                # TODO: return the cookies in the response headers for the client to use in subsequent requests.

                return Response(self._build_video_payload(video))
            return Response(
                {
                    "detail": "Video is locked. Purchase required.",
                    "creditsCost": video.price,
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        return Response(self._build_video_payload(video))


episode_detail = EpisodeDetailView.as_view()
video_detail = VideoDetailView.as_view()
video_url = VideoURLView.as_view()


def _client_ip(request) -> str:
    """Return the best-guess client IP from request headers."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class VideoPurchaseView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_video(self, video_id):
        """
        Get the video object based on the video_id.

        :param video_id: Support Slug or UUID of the video.
        """
        filters = Q(slug=video_id)
        try:
            filters |= Q(uuid=uuid.UUID(video_id))
        except ValueError:
            pass
        return get_object_or_404(Video, filters)

    def _get_episode_for_video(self, video):
        return (
            Episode.objects.filter(playlist=video)
            .order_by("episodevideo__order", "pk")
            .first()
        )

    def post(self, request, video_id):
        current_time = timezone.now()

        # confirm a valid video
        video = self._get_video(video_id)
        episode = self._get_episode_for_video(video)

        if episode is None:
            return Response(
                {"detail": "Video is not associated with an episode."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        wallet, created = Wallet.objects.get_or_create(
            user=request.user,
            site=get_current_site(request),
            credit_type=CreditTypes.CREDIT,
        )
        price = video.price or 0

        # check if the video is a free one
        if price <= 0:
            VideoReceipt.objects.get_or_create(
                user=request.user, video=video, episode=episode
            )
            emit(
                TOPIC_REVENUE,
                ChapterUnlockedEvent(
                    video_id=str(video.uuid),
                    episode_id=str(episode.uuid),
                    show_id=str(episode.show.uuid) if episode.show_id else "",
                    creator_team_id=(
                        str(episode.show.team.uuid)
                        if episode.show_id and episode.show.team_id
                        else ""
                    ),
                    user_id=str(request.user.pk),
                    credits_spent=0,
                    rev_share_rate=(
                        str(RevShareDeal.current_rate_for_show(episode.show))
                        if episode.show_id
                        else "0.70"
                    ),
                    unlock_method="free",
                    ip_address=_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                ),
            )
            return Response(
                {
                    "detail": "Video unlocked.",
                    "balance": wallet.balance,
                }
            )

        existing_receipt = (
            VideoReceipt.objects.filter(user=request.user, video=video, episode=episode)
            .order_by("-purchased_at")
            .first()
        )

        # avoid the double charge by returning when a valid receipt exists
        if existing_receipt and (
            existing_receipt.expiration_date is None
            or existing_receipt.expiration_date > current_time
        ):
            return Response(
                {
                    "detail": "Existing Valid Purchase. Video unlocked.",
                    "balance": wallet.balance,
                }
            )

        if wallet.balance < price:
            return Response(
                {
                    "detail": "Insufficient Funds. Purchase required.",
                    "price": price,
                    "balance": wallet.balance,
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        with transaction.atomic():
            locked_wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
            if locked_wallet.balance < price:
                return Response(
                    {
                        "detail": "Insufficient Funds. Purchase required.",
                        "price": price,
                        "balance": locked_wallet.balance,
                    },
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )

            locked_wallet.balance -= price
            locked_wallet.save(update_fields=["balance"])
            receipt = VideoReceipt.objects.create(
                user=request.user,
                video=video,
                episode=episode,
            )
            WalletTransaction.objects.create(
                wallet=locked_wallet,
                amount=-price,
                balance_after=locked_wallet.balance,
                transaction_type=WalletTransaction.TransactionType.VIDEO_UNLOCK,
                reference_type="video_receipt",
                reference_id=str(receipt.pk),
                metadata={
                    "video_id": str(video.uuid),
                    "video_title": video.title,
                    "episode_id": str(episode.uuid),
                },
            )

        show = episode.show if episode.show_id else None
        emit(
            TOPIC_REVENUE,
            ChapterUnlockedEvent(
                video_id=str(video.uuid),
                episode_id=str(episode.uuid),
                show_id=str(show.uuid) if show else "",
                creator_team_id=str(show.team.uuid) if show and show.team_id else "",
                user_id=str(request.user.pk),
                credits_spent=price,
                rev_share_rate=(
                    str(RevShareDeal.current_rate_for_show(show)) if show else "0.70"
                ),
                unlock_method="credits",
                ip_address=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            ),
        )

        return Response(
            {
                "detail": "Purchase successful. Video unlocked.",
                "balance": locked_wallet.balance,
            }
        )


class SignedPlaylistView(APIView):
    """
    Issues CloudFront signed cookies scoped to a video's HLS directory, then
    redirects the client to the master manifest on CloudFront.

    Cookie resource:  https://{CLOUDFRONT_DOMAIN}/videos/{uuid}/hls/*
    Redirect target:  https://{CLOUDFRONT_DOMAIN}/videos/{uuid}/hls/master.m3u8

    The wildcard cookie policy covers master.m3u8, all rendition playlists, and
    every .ts segment, so CloudFront serves the full stream without per-file signing.

    Access control mirrors VideoURLView:
      - Free videos: any client may obtain cookies.
      - Paid videos: authentication + a valid VideoReceipt are required.
    """

    permission_classes = [permissions.AllowAny]

    def _user_has_receipt(self, user, video):
        now = timezone.now()
        return (
            VideoReceipt.objects.filter(user=user, video=video)
            .filter(Q(expiration_date__isnull=True) | Q(expiration_date__gt=now))
            .exists()
        )

    def get(self, request, video_id):
        try:
            video_uuid = uuid.UUID(str(video_id))
        except ValueError:
            return Response(
                {"detail": "Invalid video ID. Must be a UUID."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        video = get_object_or_404(
            Video, uuid=video_uuid, cdn=Video.CDNChoices.S3_MEDIA_BUCKET
        )

        is_paid = (video.price or 0) > 0
        if is_paid:
            if not request.user.is_authenticated:
                return Response(
                    {"detail": "Authentication required."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            if not self._user_has_receipt(request.user, video):
                return Response(
                    {"detail": "Purchase required."},
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )

        cf_domain = getattr(settings, "CLOUDFRONT_DOMAIN", "")
        key_pair_id = getattr(settings, "CLOUDFRONT_KEY_PAIR_ID", "")
        private_key_pem = getattr(settings, "CLOUDFRONT_PRIVATE_KEY", "")

        if not all([cf_domain, key_pair_id, private_key_pem]):
            return Response(
                {"detail": "CloudFront signing is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        ttl = getattr(settings, "CLOUDFRONT_SIGNED_COOKIE_TTL", 3600)
        expires_at = timezone.now() + datetime.timedelta(seconds=ttl)

        hls_base = f"https://{cf_domain}/videos/{video.uuid}/hls/"
        manifest_url = f"{hls_base}master.m3u8"
        wildcard_resource = f"{hls_base}*"

        cookies = _generate_cf_signed_cookies(
            key_pair_id, private_key_pem, wildcard_resource, expires_at
        )

        response = HttpResponseRedirect(manifest_url)

        cookie_domain = getattr(settings, "CLOUDFRONT_COOKIE_DOMAIN", "") or None
        cookie_kwargs = dict(
            max_age=ttl,
            domain=cookie_domain,
            secure=True,
            httponly=False,
            samesite="None",
        )
        for name, value in cookies.items():
            response.set_cookie(name, value, **cookie_kwargs)

        return response


# @require_GET
# def signed_playlist(request, uuid, filename):

# try:
#     chapter = Chapter.objects.get(uuid=uuid, cdn=Chapter.CDNChoices.S3_MEDIA_BUCKET)
# except Chapter.DoesNotExist:
#     if settings.DEBUG:
#         print(
#             f"Chapter not found: uuid={uuid}, cdn={Chapter.CDNChoices.S3_MEDIA_BUCKET}"
#         )
#     raise Http404("Chapter not found")

# hls_dir = chapter.get_hls_dir()
# playlist_path = hls_dir + filename

# if settings.DEBUG:
#     print(f"Constructed playlist path: {playlist_path}")

# try:
#     playlist_file = default_storage.open(playlist_path)
#     content = playlist_file.read().decode("utf-8")
# except Exception as e:
#     if settings.DEBUG:
#         print(f"Error opening playlist file: {e}")
#     raise Http404("Playlist not found")

# signed_lines = []
# for line in content.splitlines():
#     stripped = line.strip()
#     if stripped.endswith(".ts"):
#         signed_url = default_storage.url(hls_dir + stripped)
#         signed_lines.append(signed_url)
#     elif stripped.endswith(".m3u8"):
#         signed_lines.append(reverse("signed_playlist", args=[uuid, stripped]))
#     else:
#         signed_lines.append(line)

# if settings.DEBUG:
#     print(f"Serving signed playlist for {filename} with {len(signed_lines)} lines")
#     print("\n".join(signed_lines))

# return HttpResponse(
#     "\n".join(signed_lines), content_type="application/vnd.apple.mpegurl"
# )


class ShowsMustSeeView(ListAPIView):
    serializer_class = ShowSerializer

    def get_queryset(self):
        limit = self.request.query_params.get("limit", 10)
        return Show.objects.filter(tags__name="Must See")[
            : int(limit)
        ]  # probably a better way to do this


class ShowsCategoryView(ListAPIView):
    serializer_class = ShowSerializer

    def get_queryset(self):
        category_slug = self.kwargs.get("category")
        tag = get_object_or_404(Tag, slug=category_slug, tagtype=Tag.TagType.CALL_OUT)
        return Show.objects.filter(tags=tag)


# MOCK_SHOW_DETAILS = {
#     "id": "showId",
#     "title": "Cosmic Frontiers",
#     "description": "An epic space exploration series following humanity's journey to the stars.",
#     "longDescription": "Set in the year 2157, Cosmic Frontiers follows the crew of the starship Endeavor as they embark on humanity's most ambitious mission: establishing the first permanent colonies beyond the solar system. Through breathtaking visuals and compelling storytelling, this series explores themes of discovery, survival, and what it means to be human in the vast expanse of space. Each episode combines cutting-edge science with thrilling adventure, featuring realistic space physics and extraterrestrial encounters that challenge our understanding of the universe.",, # noqa: E501
#     "poster": "https://images.unsplash.com/photo-1690906379371-9513895a2615?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxzY2ktZmklMjBzcGFjZSUyMHNlcmllcyUyMHBvc3RlcnxlbnwxfHx8fDE3NTY0OTU0OTB8MA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral",, # noqa: E501
#     "backdropImage": "https://images.unsplash.com/photo-1690906379371-9513895a2615?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxzY2ktZmklMjBzcGFjZSUyMHNlcmllcyUyMHBvc3RlcnxlbnwxfHx8fDE3NTY0OTU0OTB8MA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral", # noqa: E501
#     "rating": 4.8,
#     "year": 2024,
#     "totalEpisodes": 24,
#     "language": "English",
#     "creator": "Sarah Chen",  # Team
#     "tags": ["Sci-Fi", "Space Opera", "Drama", "Adventure", "Action"],
#     "seasons": [
#         {
#             "id": "season-1",
#             "title": "Season 1: The Journey Begins",
#             "seasonNumber": 1,
#             "episodes": [
#                 {
#                     "id": "ep-1-1",
#                     "title": "Departure Protocol",
#                     "description": "The crew of the Endeavor prepares for humanity's greatest journey as they leave Earth behind and venture into the unknown depths of space.",
#                     "duration": 3420,  # // 57 minutes
#                     "rating": 4.7,
#                     "chapterCount": 8,
#                     "episodeNumber": 1,
#                     "poster": "https://images.unsplash.com/photo-1462332420958-a05d1e002413?w=400&h=225&fit=crop",
#                     "releaseDate": "2024-03-15",
#                     "isLocked": False,
#                 },
#                 {
#                     "id": "ep-1-2",
#                     "title": "First Contact Protocols",
#                     "description": "Strange signals from the Proxima Centauri system force the crew to question everything they thought they knew about alien life.",
#                     "duration": 3240,  # // 54 minutes
#                     "rating": 4.9,
#                     "chapterCount": 7,
#                     "episodeNumber": 2,
#                     "poster": "https://images.unsplash.com/photo-1541185933-ef5d8ed016c2?w=400&h=225&fit=crop",
#                     "releaseDate": "2024-03-22",
#                     "isLocked": False,
#                 },
#                 {
#                     "id": "ep-1-3",
#                     "title": "The Anomaly",
#                     "description": "A mysterious space-time anomaly threatens to tear the ship apart while revealing secrets about the nature of faster-than-light travel.",
#                     "duration": 3600,  # // 60 minutes
#                     "rating": 4.8,
#                     "chapterCount": 9,
#                     "episodeNumber": 3,
#                     "poster": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&h=225&fit=crop",
#                     "releaseDate": "2024-03-29",
#                     "isLocked": True,
#                 },
#                 {
#                     "id": "ep-1-4",
#                     "title": "Gravity's Edge",
#                     "description": "The crew encounters a rogue planet with impossible gravitational properties that defies all known laws of physics.",
#                     "duration": 3480,  # // 58 minutes
#                     "rating": 4.6,
#                     "chapterCount": 8,
#                     "episodeNumber": 4,
#                     "poster": "https://images.unsplash.com/photo-1517002566555-fe91e6b07b6e?w=400&h=225&fit=crop",
#                     "releaseDate": "2024-04-05",
#                     "isLocked": True,
#                 },
#             ],
#         },
#         {
#             "id": "season-2",
#             "title": "Season 2: New Worlds",
#             "seasonNumber": 2,
#             "episodes": [
#                 {
#                     "id": "ep-2-1",
#                     "title": "Colonial Dawn",
#                     "description": "The Endeavor reaches Kepler-442b and begins establishing humanity's first interstellar colony, but the planet holds unexpected dangers.",
#                     "duration": 3660,  # // 61 minutes
#                     "rating": 4.9,
#                     "chapterCount": 10,
#                     "episodeNumber": 1,
#                     "poster": "https://images.unsplash.com/photo-1519904981063-b0cf448d479e?w=400&h=225&fit=crop",
#                     "releaseDate": "2024-09-15",
#                     "isLocked": True,
#                 },
#                 {
#                     "id": "ep-2-2",
#                     "title": "The Inhabitants",
#                     "description": "First contact with the planet's indigenous species leads to complex diplomatic challenges and moral dilemmas for the human colonists.",
#                     "duration": 3420,  # // 57 minutes
#                     "rating": 4.8,
#                     "chapterCount": 8,
#                     "episodeNumber": 2,
#                     "poster": "https://images.unsplash.com/photo-1543722530-d2c3201371e7?w=400&h=225&fit=crop",
#                     "releaseDate": "2024-09-22",
#                     "isLocked": True,
#                 },
#             ],
#         },
#     ],
# }


class ShowDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, show_id):
        show = get_object_or_404(Show, slug=show_id)

        serializer = ShowSerializer(show, context={"request": request})
        return Response(serializer.data)


# ── Video rating (like / dislike) ─────────────────────────────────────────────


def _sync_video_rating(video: Video) -> None:
    """
    Recompute rating_value and rating_count on *video* from its VideoRating rows,
    excluding neutral (1) reactions.

    rating_value is stored as 0–50 (like=2 maps to 50, dislike=0 maps to 0).
    rating_count counts only non-neutral rows.
    """
    from django.db.models import Avg, Count

    qs = VideoRating.objects.filter(video=video).exclude(
        rating=VideoRating.Rating.NEUTRAL
    )
    agg = qs.aggregate(avg=Avg("rating"), cnt=Count("id"))
    count = agg["cnt"] or 0
    if count == 0:
        video.rating_value = None
        video.rating_count = 0
    else:
        # avg is 0.0–2.0; scale to 0–50 to match existing convention
        video.rating_value = round((agg["avg"] / 2.0) * 50)
        video.rating_count = count
    video.save(update_fields=["rating_value", "rating_count"])


@api_view(["POST", "GET"])
@permission_classes([permissions.IsAuthenticated])
def video_rate(request, video_id):
    """
    GET  /video/<video_id>/rate  — return the current user's rating for this video.
    POST /video/<video_id>/rate  — submit or update a rating.

    POST body: { "rating": 0 | 1 | 2 }
      0 = dislike, 1 = neutral (removes reaction), 2 = like

    Response: { "rating": <int>, "rating_value": <int|null>, "rating_count": <int> }
    """
    video = get_object_or_404(
        Video.objects.select_related("playlist__show"), slug=video_id, active=True
    )

    if request.method == "GET":
        try:
            vr = VideoRating.objects.get(user=request.user, video=video)
            rating = vr.rating
        except VideoRating.DoesNotExist:
            rating = VideoRating.Rating.NEUTRAL
        return Response({"rating": rating})

    # POST
    raw = request.data.get("rating")
    if raw is None:
        return Response(
            {"detail": "rating is required."}, status=status.HTTP_400_BAD_REQUEST
        )
    try:
        new_rating = int(raw)
    except (TypeError, ValueError):
        return Response(
            {"detail": "rating must be 0, 1, or 2."}, status=status.HTTP_400_BAD_REQUEST
        )
    if new_rating not in (0, 1, 2):
        return Response(
            {"detail": "rating must be 0, 1, or 2."}, status=status.HTTP_400_BAD_REQUEST
        )

    # Capture the existing rating before overwriting so we can track changes.
    try:
        existing_vr = VideoRating.objects.get(user=request.user, video=video)
        previous_rating = existing_vr.rating
    except VideoRating.DoesNotExist:
        previous_rating = None

    VideoRating.objects.update_or_create(
        user=request.user,
        video=video,
        defaults={"rating": new_rating},
    )
    _sync_video_rating(video)
    video.refresh_from_db(fields=["rating_value", "rating_count"])

    episode = video.playlist  # Video.playlist is FK → Episode
    ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[
        0
    ].strip() or request.META.get("REMOTE_ADDR", "")
    emit(
        TOPIC_ENGAGEMENT,
        VideoRatingEvent(
            user_id=str(request.user.pk),
            video_id=str(video.uuid),
            episode_id=str(episode.uuid) if episode else "",
            show_id=str(episode.show.uuid) if episode else "",
            rating=new_rating,
            previous_rating=previous_rating,
            session_id=request.META.get("HTTP_X_SESSION_ID", ""),
            ip_address=ip,
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        ),
    )

    return Response(
        {
            "rating": new_rating,
            "rating_value": video.rating_value,
            "rating_count": video.rating_count,
        }
    )
