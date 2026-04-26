from django.conf import settings
from django.http import JsonResponse


class MaintenanceMiddleware:
    """
    Returns a 503 JSON response for all requests when MAINTENANCE_MODE is True.
    Paths listed in MAINTENANCE_BYPASS_PATHS are always allowed through.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "MAINTENANCE_MODE", False):
            return self.get_response(request)

        bypass_paths = getattr(settings, "MAINTENANCE_BYPASS_PATHS", [])
        if any(request.path.startswith(path) for path in bypass_paths):
            return self.get_response(request)

        return JsonResponse(
            {"detail": "Service temporarily unavailable. Please try again later."},
            status=503,
        )
