import datetime
import random
import uuid
from typing import Any, Dict, List, Optional

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

# In-memory per-user viewing history store (dev-only)
# Keyed by "user" (for now we use a session_key or "default")
_VIEWING_HISTORY: Dict[str, List[Dict[str, Any]]] = {}


def now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"


def make_history_item(show_id: Optional[str] = None, idx: int = 1) -> Dict[str, Any]:
    hid = str(uuid.uuid4())
    sid = show_id or str(uuid.uuid4())
    title = f"Demo Show {idx}"
    return {
        "id": hid,
        "showId": sid,
        "title": title,
        "thumbnail": f"https://picsum.photos/seed/{hid}/400/225",
        "contentType": random.choice(["movie", "episode", "clip"]),
        "watchedAt": now_iso(),
        "progress": random.randint(0, 100),
        "duration": random.randint(5, 180),
    }


def _get_store_key(request):
    # Prefer authenticated user id if available (request.user.id),
    # otherwise use session_key or a default key.
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        return f"user:{getattr(user, 'id', 'anon')}"
    # Create session if not present
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key
    return f"session:{session_key}"


@api_view(["GET"])
def viewing_history_list(request):
    """
    GET /api/v1/viewing-history
    Query params: limit, offset, contentType, startDate, endDate
    """
    key = _get_store_key(request)
    items = _VIEWING_HISTORY.get(key, [])
    # Simple filtering based on query params
    content_type = request.query_params.get("contentType")
    if content_type:
        items = [i for i in items if i.get("contentType") == content_type]
    # pagination
    try:
        limit = int(request.query_params.get("limit", len(items)))
        offset = int(request.query_params.get("offset", 0))
    except ValueError:
        limit = len(items)
        offset = 0
    slice_items = items[offset : offset + limit]  # noqa: E203
    return Response(slice_items)


@api_view(["POST"])
def viewing_history_add(request):
    """
    POST /api/v1/viewing-history/add
    Body: { showId, progress, duration? }
    Returns created ViewingHistoryItem
    """
    key = _get_store_key(request)
    payload = request.data or {}
    show_id = payload.get("showId") or str(uuid.uuid4())
    progress = int(payload.get("progress", 0))
    duration = int(payload.get("duration", 0))
    item = make_history_item(show_id=show_id, idx=random.randint(1, 1000))
    item["progress"] = progress
    item["duration"] = duration or item["duration"]
    item["watchedAt"] = now_iso()
    _VIEWING_HISTORY.setdefault(key, []).insert(0, item)  # newest first
    return Response(item, status=status.HTTP_201_CREATED)


@api_view(["PUT"])
def viewing_history_update_progress(request, history_id: str):
    """
    PUT /api/v1/viewing-history/<history_id>/progress
    Body: { progress }
    Returns the updated item
    """
    key = _get_store_key(request)
    items = _VIEWING_HISTORY.get(key, [])
    payload = request.data or {}
    progress = int(payload.get("progress", 0))
    for it in items:
        if it.get("id") == history_id:
            it["progress"] = progress
            it["watchedAt"] = now_iso()
            return Response(it)
    return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(["DELETE"])
def viewing_history_remove(request, history_id: str):
    """
    DELETE /api/v1/viewing-history/<history_id>
    """
    key = _get_store_key(request)
    items = _VIEWING_HISTORY.get(key, [])
    new_items = [i for i in items if i.get("id") != history_id]
    _VIEWING_HISTORY[key] = new_items
    return Response({"success": True})


@api_view(["DELETE"])
def viewing_history_clear(request):
    """
    DELETE /api/v1/viewing-history/clear
    """
    key = _get_store_key(request)
    _VIEWING_HISTORY[key] = []
    return Response({"success": True})


@api_view(["GET"])
def viewing_history_continue_watching(request):
    """
    GET /api/v1/viewing-history/continue-watching?limit=10
    Returns items with progress > 0 and < 100
    """
    key = _get_store_key(request)
    items = _VIEWING_HISTORY.get(key, [])
    continue_items = [i for i in items if 0 < i.get("progress", 0) < 100]
    limit = int(request.query_params.get("limit", 10))
    return Response(continue_items[:limit])


@api_view(["GET"])
def viewing_history_recent(request):
    """
    GET /api/v1/viewing-history/recent?limit=20
    Returns most recent items
    """
    key = _get_store_key(request)
    items = _VIEWING_HISTORY.get(key, [])
    limit = int(request.query_params.get("limit", 20))
    return Response(items[:limit])


@api_view(["GET"])
def viewing_history_stats(request):
    """
    GET /api/v1/viewing-history/stats?period=week|month|year|all
    Returns aggregated watch-time stats
    """
    period = request.query_params.get("period", "week")  # noqa: F841
    # mock stats
    total_minutes = random.randint(100, 5000)
    total_shows = random.randint(1, 100)
    avg_per_day = round(total_minutes / 7.0, 2)
    by_content_type = {
        "movie": random.randint(0, total_minutes),
        "episode": random.randint(0, total_minutes),
    }
    by_day = [
        {
            "date": (datetime.datetime.utcnow() - datetime.timedelta(days=i))
            .date()
            .isoformat(),
            "minutes": random.randint(0, 300),
        }
        for i in range(7)
    ]
    return Response(
        {
            "totalMinutes": total_minutes,
            "totalShows": total_shows,
            "averagePerDay": avg_per_day,
            "byContentType": by_content_type,
            "byDay": by_day,
        }
    )


@api_view(["GET"])
def viewing_history_recommendations(request):
    """
    GET /api/v1/viewing-history/recommendations?limit=10
    Returns a list of recommended content based on history (mock)
    """
    limit = int(request.query_params.get("limit", 10))
    recs = []
    for i in range(limit):
        recs.append(
            {
                "id": str(uuid.uuid4()),
                "title": f"Recommended Show {i+1}",
                "thumbnail": f"https://picsum.photos/seed/reco{i}/400/225",
                "reason": "Based on your watch history",
            }
        )
    return Response(recs)


@api_view(["GET"])
def viewing_history_export(request):
    """
    GET /api/v1/viewing-history/export?format=csv|json
    Returns a downloadUrl
    """
    fmt = request.query_params.get("format", "json")
    return Response(
        {"downloadUrl": f"https://example.com/viewing-history/export.{fmt}"}
    )


@api_view(["GET"])
def viewing_history_check(request, content_id: str):
    """
    GET /api/v1/viewing-history/check/<content_id>
    Returns { watched: boolean, progress?: number, lastWatchedAt?: string }
    """
    key = _get_store_key(request)
    items = _VIEWING_HISTORY.get(key, [])
    for it in items:
        if it.get("showId") == content_id:
            return Response(
                {
                    "watched": True,
                    "progress": it.get("progress", 0),
                    "lastWatchedAt": it.get("watchedAt"),
                }
            )
    return Response({"watched": False})
