# from unittest.mock import patch

# from django.contrib.auth import get_user_model
# from django.test import Client, TestCase
# from django.urls import reverse

# User = get_user_model()


# class TestEventMachineViews(TestCase):
#     def setUp(self):
#         self.client = Client()

#     @patch("event_machine.views.log_event")
#     def test_log_playback_event(self, mock_log_event):
#         """
#         Test the log_playback_event view.
#         """
#         url = reverse("event_machine:log_playback_event")
#         data = {
#             "video_id": "test_video",
#             "user_id": "123",
#             "state": "start",
#         }

#         response = self.client.post(url, data)

#         self.assertEqual(response.status_code, 200)
#         self.assertJSONEqual(
#             response.content.decode(),
#             {"status": "success", "message": "Playback event logged."},
#         )

#         # Verify log_event was called with the correct arguments
#         mock_log_event.assert_called_once_with(
#             "playback",
#             "123",
#             request=response.wsgi_request,
#             video_id="test_video",
#             state="start",
#         )
