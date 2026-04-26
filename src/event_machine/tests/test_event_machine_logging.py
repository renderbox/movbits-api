# from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase  # ,Client

# from event_machine.logging import log_event
# from event_machine.models import LogBlock
from microdrama.models import Chapter, Episode, Series, Team

# from django.urls import reverse


User = get_user_model()


class MockRedis:
    def __init__(self):
        self.storage = {}

    def rpush(self, key, value):
        if key not in self.storage:
            self.storage[key] = []
        self.storage[key].append(value)

    def lrange(self, key, start, end):
        return self.storage.get(key, [])[start:end]

    def delete(self, key):
        if key in self.storage:
            del self.storage[key]


class LogEventTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="test_user")  # Use dynamic user model
        self.episode = Episode.objects.create(
            title="Test Episode",
            series=Series.objects.create(
                title="Test Series", team=Team.objects.create(name="Test Team")
            ),
        )
        self.chapter = Chapter.objects.create(
            title="Test Chapter",
            video_url="test_video_url",
            chapter_number=1,  # Added valid chapter_number
            cdn=Chapter.CDNChoices.YOUTUBE,  # Use IntegerChoices for CDN
            episode=self.episode,  # Associate with the created episode
        )
        self.state = "start"


# TODO: Look into why this test is locking up.
#     @patch("redis.Redis.from_url")
#     def test_log_event_creates_log_block(self, mock_redis):
#         mock_redis.return_value = MockRedis()

#         log_event("playback", self.user.id, video_id=self.chapter.id, state=self.state)

#         log_blocks = LogBlock.objects.filter(
#             group="playback",
#             user=self.user.id,
#         )
#         self.assertEqual(log_blocks.count(), 1)

#         log_data = log_blocks.first().log_data
#         self.assertTrue(
#             any(
#                 event["video_id"] == self.chapter.id and event["state"] == self.state
#                 for event in log_data
#             )
#         )


# class LogPlaybackEventAPITests(TestCase):
#     def setUp(self):
#         self.client = Client()
#         self.url = reverse("event_machine:log_playback_event")
#         self.user = User.objects.create(username="test_user")  # Use dynamic user model
#         self.video_id = "test_video"
#         self.state = "start"

#     @patch("redis.Redis.from_url")
#     def test_log_playback_event_success(self, mock_redis):
#         mock_redis.return_value = MockRedis()

#         response = self.client.post(
#             self.url,
#             {
#                 "video_id": self.video_id,
#                 "user_id": self.user.id,
#                 "state": self.state,
#             },
#         )

#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(response.json()["status"], "success")

#         log_blocks = LogBlock.objects.filter(user=self.user.id)
#         self.assertEqual(
#             sum(
#                 1
#                 for block in log_blocks
#                 if any(
#                     event.get("video_id") == self.video_id for event in block.log_data
#                 )
#             ),
#             1,
#         )
#         self.assertIn(
#             self.state, [event["state"] for event in log_blocks.first().log_data]
#         )

# def test_log_playback_event_missing_parameters(self):
#     response = self.client.post(self.url, {"video_id": self.video_id})

#     self.assertEqual(response.status_code, 400)
#     self.assertIn("error", response.json())


#     def test_log_playback_event_invalid_method(self):
#         response = self.client.get(self.url)

#         self.assertEqual(response.status_code, 405)
#         self.assertIn("error", response.json())

#     @patch("event_machine.views.log_event", autospec=True)
#     def test_log_playback_event_with_ip(self, mock_log_event):
#         """
#         Test the log_playback_event view with IP address logging.
#         """
#         response = self.client.post(
#             self.url,
#             {
#                 "video_id": self.video_id,
#                 "user_id": self.user.id,  # Ensure user_id is passed as an integer
#                 "state": self.state,
#             },
#             **{"HTTP_REMOTE_ADDR": "192.11.0.1"},
#         )

#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(response.json()["status"], "success")

#         # Verify log_event was called with the correct IP address
#         mock_log_event.assert_called_once_with(
#             "playback",
#             str(self.user.id),  # Ensure user_id is returned as a string
#             request=response.wsgi_request,
#             video_id=self.video_id,
#             state=self.state,
#         )
