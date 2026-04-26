import json
import logging
import os

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseNotFound, JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from event_machine.logging import log_event

from .flush_logs import flush_time_block
from .redis_client import redis_client as r

# Configure logger
logger = logging.getLogger(__name__)


class FlushLogsAdminView(LoginRequiredMixin, View):
    """
    Admin view for flushing logs.

    This view restricts access to superusers and displays Redis keys
    related to log buffers.
    """

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests to display log buffer keys.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            HttpResponse: The rendered admin page or a 404 response.
        """
        if not request.user.is_superuser:
            return HttpResponseNotFound("Page not found")

        keys = r.keys("log_buffer:*")
        parsed_keys = sorted(k.decode() for k in keys)

        context = {"log_blocks": parsed_keys, "api_key": os.getenv("FLUSH_API_KEY", "")}
        return render(request, "event_machine/flush_logs_admin.html", context)


@method_decorator(csrf_exempt, name="dispatch")
class FlushLogsApiView(View):
    """
    API view for flushing logs.

    Requires an API key for authorization and flushes logs for predefined groups.
    """

    def post(self, request, *args, **kwargs):
        expected_key = os.getenv("FLUSH_API_KEY")
        provided_key = request.headers.get("X-API-Key")
        # Check for API key or superuser permission
        if (
            not (expected_key and expected_key == provided_key)
            and not request.user.is_superuser
        ):
            return JsonResponse({"error": "Unauthorized"}, status=403)

        # Parse the log_blocks from the request body
        body = json.loads(request.body)
        log_blocks = body.get("log_blocks", [])

        if not log_blocks:
            return JsonResponse({"error": "No log blocks provided"}, status=400)

        flushed = []
        for log_block in log_blocks:
            try:
                log_base, group, time_block = log_block.split(
                    ":", 2
                )  # Split into exactly two parts
                count = flush_time_block(group, time_block)
                if count:
                    flushed.append(f"{group}:{time_block} ({count} events)")
            except ValueError:
                return JsonResponse(
                    {"error": f"Invalid log block format: {log_block}"}, status=400
                )

        return JsonResponse({"status": "flushed", "keys": flushed})


@csrf_exempt
def log_playback_event(request):
    """
    API endpoint to log playback events for YouTube videos.

    Expects POST data with:
    - video_id: ID of the YouTube video.
    - user_id: ID of the user.
    - state: Playback state ('start' or 'stop').
    """
    if request.method != "POST":
        log_event(
            "playback",  # group
            request.user.id,  # user_id
            request=request,  # Pass the request object
            errors="Invalid request method.",
        )

        return JsonResponse({"error": "Invalid request method."}, status=405)

    data = request.POST
    video_id = data.get("video_id")
    user_id = data.get("user_id")
    state = data.get("state")

    if not video_id or not user_id or not state:

        log_event(
            "playback",  # group
            user_id,  # user_id
            request=request,  # Pass the request object
            errors="Missing required parameters.",
        )

        return JsonResponse({"error": "Missing required parameters."}, status=400)

    log_event(
        "playback",  # group
        user_id,  # user_id
        request=request,  # Pass the request object
        video_id=video_id,
        state=state,
    )

    return JsonResponse({"status": "success", "message": "Playback event logged."})
