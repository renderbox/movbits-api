import datetime
import random
import uuid

# from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from shows.models import Episode

from .serializers import TopPerformingEpisodeSerializer


def now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"


def make_kpis():
    return {
        "views": random.randint(1000, 100000),
        "viewsDelta": random.randint(-500, 500),
        "watchTime": random.randint(1000, 50000),
        "watchTimeDelta": random.randint(-500, 500),
        "revenue": round(random.random() * 10000, 2),
        "revenueDelta": round(random.uniform(-500, 500), 2),
        "subscribers": random.randint(10, 10000),
        "subscribersDelta": random.randint(-50, 200),
    }


def make_analytics_data(content_id=None):
    return {
        "showId": content_id or str(uuid.uuid4()),
        "showTitle": "Demo Content",
        "contentType": "movie",
        "totalViews": random.randint(100, 100000),
        "uniqueViewers": random.randint(50, 90000),
        "watchTime": random.randint(100, 50000),
        "averageViewDuration": random.uniform(1, 120),
        "completionRate": round(random.uniform(10, 100), 2),
        "engagement": round(random.uniform(0, 100), 2),
        "revenue": round(random.random() * 1000, 2),
        "conversionRate": round(random.uniform(0, 10), 2),
        "topCountries": [
            {
                "country": "US",
                "views": random.randint(10, 10000),
                "percentage": round(random.uniform(1, 60), 2),
            },
            {
                "country": "GB",
                "views": random.randint(10, 5000),
                "percentage": round(random.uniform(1, 30), 2),
            },
        ],
        "viewsOverTime": [
            {
                "date": now_iso(),
                "views": random.randint(0, 1000),
                "watchTime": random.randint(0, 1000),
            }
            for _ in range(7)
        ],
        "deviceBreakdown": [
            {
                "device": d,
                "views": random.randint(0, 1000),
                "percentage": round(random.uniform(0, 100), 2),
            }
            for d in ["desktop", "mobile", "tv"]
        ],
        "audienceRetention": [
            {"time": t, "percentage": round(random.uniform(0, 100), 2)}
            for t in [10, 30, 60, 120]
        ],
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def kpis(request):
    return Response(make_kpis())


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_overview(request):
    return Response(
        {
            "kpis": make_kpis(),
            "recentShows": [
                {"id": str(uuid.uuid4()), "title": f"Recent {i}"} for i in range(1, 6)
            ],
            "topPerformers": [
                {"id": str(uuid.uuid4()), "title": f"Top {i}"} for i in range(1, 6)
            ],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def content_analytics(request, *args, **kwargs):
    # Works for shows/<id>/analytics, series/<id>/analytics, etc.
    content_id = (
        kwargs.get("show_id")
        or kwargs.get("franchise_id")
        or kwargs.get("series_id")
        or kwargs.get("episode_id")
        or None
    )
    return Response(make_analytics_data(content_id))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_range(request, content_id):
    start = request.query_params.get("start")  # noqa: F841
    end = request.query_params.get("end")  # noqa: F841
    # Return an array of time series points
    points = [
        {
            "date": (datetime.datetime.utcnow() - datetime.timedelta(days=i))
            .date()
            .isoformat(),
            "views": random.randint(0, 500),
            "watchTime": random.randint(0, 200),
        }
        for i in range(7)
    ]
    return Response(points)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_popularity(request, content_id):
    metrics = [
        {
            "period": p,
            "views": random.randint(0, 10000),
            "growth": round(random.uniform(-1, 2), 2),
        }
        for p in ["7d", "30d", "90d"]
    ]
    return Response(metrics)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_geography(request, content_id):
    return Response(
        {
            "countries": [
                {"country": "US", "views": 1000, "percentage": 50.0},
                {"country": "CA", "views": 200, "percentage": 10.0},
            ]
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_devices(request, content_id):
    return Response(
        {
            "devices": [
                {"device": "desktop", "views": 1000, "percentage": 60},
                {"device": "mobile", "views": 600, "percentage": 36},
            ]
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_retention(request, content_id):
    return Response(
        {
            "retention": [
                {"time": 10, "percentage": 80.5},
                {"time": 30, "percentage": 60.0},
                {"time": 60, "percentage": 35.2},
            ]
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_revenue(request, content_id):
    timeseries = [
        {
            "date": (datetime.datetime.utcnow() - datetime.timedelta(days=i))
            .date()
            .isoformat(),
            "views": random.randint(0, 500),
            "watchTime": random.randint(0, 200),
        }
        for i in range(7)
    ]
    return Response(
        {
            "totalRevenue": round(random.random() * 1000, 2),
            "revenueByDate": timeseries,
            "conversionRate": round(random.uniform(0, 10), 2),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_engagement(request, content_id):
    return Response(
        {
            "averageWatchTime": random.uniform(1, 120),
            "completionRate": round(random.uniform(10, 100), 2),
            "engagement": round(random.uniform(0, 100), 2),
            "likes": random.randint(0, 500),
            "comments": random.randint(0, 200),
            "shares": random.randint(0, 100),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_top_performing(request):
    """
    Top performing episodes for a team.
    GET /api/v1/analytics/analytics/top-performing?limit=10&sortBy=views&teamId=<uuid>

    views, revenue, and engagement are faked with random values until real
    analytics data is wired up.
    """
    limit = int(request.query_params.get("limit", 10))
    team_id = request.query_params.get("teamId")

    qs = Episode.objects.select_related("show").filter(active=True)
    if team_id:
        qs = qs.filter(show__team__uuid=team_id)

    episodes = qs.order_by("-updated_at")[:limit]
    serializer = TopPerformingEpisodeSerializer(
        episodes, many=True, context={"request": request}
    )
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def analytics_compare(request):
    payload = request.data or {}
    content_ids = payload.get("contentIds", [])
    comparison = {cid: make_analytics_data(cid) for cid in content_ids}
    return Response({"comparison": comparison})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_export(request, content_id):
    fmt = request.query_params.get("format", "json")
    return Response(
        {"downloadUrl": f"https://example.com/analytics/{content_id}/export.{fmt}"}
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_realtime(request, content_id):
    return Response(
        {
            "currentViewers": random.randint(0, 200),
            "viewsLastHour": random.randint(0, 1000),
            "recentCountries": ["US", "GB", "CA"],
        }
    )


def _parse_days(time_range: str) -> int:
    if time_range == "7d":
        return 7
    if time_range == "90d":
        return 90
    return 30


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def views_over_time(request):
    """
    Total views over a period of time (7d, 30d, 90d).
    GET /api/v1/analytics/analytics/views-over-time?timeRange=30d
    NOTE: currently returning mock data with a similar pattern to views, but in production this would be based on actual view data
    and could have a different pattern (e.g. more spikes around holidays, etc.)
    """
    days = _parse_days(request.query_params.get("timeRange", "30d"))
    today = datetime.date.today()
    spike_day = int(days * 0.66)

    data = []
    for i in range(days):
        date = today - datetime.timedelta(days=(days - 1 - i))
        is_weekend = date.weekday() >= 5  # Sat=5, Sun=6
        trend = 40000 + (i / days) * 25000
        weekend_factor = 0.7 if is_weekend else 1.0
        spike_factor = 2.8 if i == spike_day else (1.6 if i == spike_day + 1 else 1.0)
        noise = random.uniform(-3000, 3000)
        views = max(0, int(trend * weekend_factor * spike_factor + noise))
        data.append(
            {
                "date": date.isoformat(),
                "views": views,
                "revenue": 0,
                "engagement": random.randint(72, 87),
            }
        )

    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def revenue_over_time(request):
    """
    Total revenue over a period of time (7d, 30d, 90d).
    GET /api/v1/analytics/analytics/revenue-over-time?timeRange=30d
    NOTE: currently returning mock data with a similar pattern to views, but in production this would be based on actual revenue data
    and could have a different pattern (e.g. more spikes around holidays, etc.)
    """
    days = _parse_days(request.query_params.get("timeRange", "30d"))
    today = datetime.date.today()
    spike_day = int(days * 0.66)

    data = []
    for i in range(days):
        date = today - datetime.timedelta(days=(days - 1 - i))
        is_weekend = date.weekday() >= 5
        trend = 6000 + (i / days) * 8000
        weekend_factor = 0.75 if is_weekend else 1.0
        spike_factor = 3.1 if i == spike_day else (1.7 if i == spike_day + 1 else 1.0)
        noise = random.uniform(-600, 600)
        revenue = max(0, int(trend * weekend_factor * spike_factor + noise))
        data.append(
            {
                "date": date.isoformat(),
                "views": 0,
                "revenue": revenue,
                "engagement": random.randint(72, 87),
            }
        )

    return Response(data)
