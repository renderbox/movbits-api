from django.contrib.auth import get_user_model
from django.test import TestCase

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
        self.user = User.objects.create(username="test_user")

    # TODO: wire tests to shows.Video once event_machine test fixtures
    # are updated. All test cases below are temporarily disabled.

    # @patch("redis.Redis.from_url")
    # def test_log_event_creates_log_block(self, mock_redis):
    #     ...
