from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """
    GET /api/v1/maintenance/health
    Always returns 200 — used by Cloud Run health checks and load balancer probes.
    Also reports whether the API is currently in maintenance mode.
    """
    return Response(
        {
            "status": "ok",
            "maintenance": getattr(settings, "MAINTENANCE_MODE", False),
        }
    )
