from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from core.models import ConsentRecord

CONSENT_VERSION = "1.0"

_CONSENT_ITEMS = [
    {
        "id": "necessary",
        "category": "necessary",
        "name": "Necessary Cookies",
        "required": True,
        "enabled": True,
        "services": [
            "Authentication",
            "Session Management",
            "Security",
            "Load Balancing",
        ],
    },
    {
        "id": "functional",
        "category": "functional",
        "name": "Functional Cookies",
        "required": False,
        "enabled": False,
        "services": [
            "Language Preferences",
            "Playback Settings",
            "Subtitle Preferences",
        ],
    },
    {
        "id": "analytics",
        "category": "analytics",
        "name": "Analytics Cookies",
        "required": False,
        "enabled": False,
        "services": ["Usage Statistics", "Performance Monitoring", "Error Tracking"],
    },
    {
        "id": "marketing",
        "category": "marketing",
        "name": "Marketing Cookies",
        "required": False,
        "enabled": False,
        "services": [
            "Personalized Recommendations",
            "Ad Targeting",
            "Cross-site Tracking",
        ],
    },
    {
        "id": "preferences",
        "category": "preferences",
        "name": "Preference Cookies",
        "required": False,
        "enabled": False,
        "services": ["Theme Settings", "Notification Preferences", "Content Filters"],
    },
]


def _ip(request):
    return request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[
        0
    ].strip() or request.META.get("REMOTE_ADDR", "")


@api_view(["GET"])
@permission_classes([AllowAny])
def consent_items(request):
    return Response({"version": CONSENT_VERSION, "items": _CONSENT_ITEMS})


@api_view(["POST"])
@permission_classes([AllowAny])
def save_consent(request):
    preferences = request.data.get("preferences", {})
    version = request.data.get("version", CONSENT_VERSION)

    preferences.setdefault("necessary", True)

    user = request.user if request.user.is_authenticated else None
    session_key = request.session.session_key or ""
    if not session_key and not request.user.is_authenticated:
        request.session.create()
        session_key = request.session.session_key or ""

    ConsentRecord.objects.create(
        user=user,
        session_key=session_key,
        preferences=preferences,
        version=version,
        ip_address=_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    latest = (
        ConsentRecord.objects.filter(user=user, session_key=session_key)
        .order_by("-created_at")
        .first()
    )

    return Response(
        {
            "preferences": latest.preferences,
            "version": latest.version,
            "timestamp": latest.created_at.isoformat(),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_consent(request):
    record = (
        ConsentRecord.objects.filter(user=request.user).order_by("-created_at").first()
    )
    if not record:
        return Response({"preferences": None, "version": None, "timestamp": None})
    return Response(
        {
            "preferences": record.preferences,
            "version": record.version,
            "timestamp": record.created_at.isoformat(),
        }
    )


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_user_consent(request):
    preferences = request.data.get("preferences", {})
    version = request.data.get("version", CONSENT_VERSION)

    preferences.setdefault("necessary", True)

    record = ConsentRecord.objects.create(
        user=request.user,
        session_key="",
        preferences=preferences,
        version=version,
        ip_address=_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    return Response(
        {
            "preferences": record.preferences,
            "version": record.version,
            "timestamp": record.created_at.isoformat(),
        }
    )
