from django.urls import path

from .views import FlushLogsAdminView, FlushLogsApiView, log_playback_event

app_name = "event_machine"

urlpatterns = [
    path("flush-logs/", FlushLogsAdminView.as_view(), name="flush_logs_admin"),
    path("api/flush-logs/", FlushLogsApiView.as_view(), name="flush_logs_api"),
    path("api/log-playback-event/", log_playback_event, name="log_playback_event"),
]
