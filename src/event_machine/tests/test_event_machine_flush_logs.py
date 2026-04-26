from unittest.mock import MagicMock, patch

from django.test import TestCase

from event_machine.flush_logs import flush_time_block


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


class FlushLogsTests(TestCase):
    @patch("event_machine.flush_logs.r")
    @patch("event_machine.flush_logs.s3")
    def test_flush_time_block(self, mock_s3, mock_redis):
        """
        Test flushing logs for a specific time block.
        """
        # Mock Redis interactions
        mock_redis.lrange.return_value = [b'{"key": "value"}']
        mock_redis.delete.return_value = None

        # Mock S3 interactions
        mock_s3.client.return_value = MagicMock()

        # Call the function
        flushed_count = flush_time_block("test_group", "20230530T1200")
        self.assertIsInstance(flushed_count, int)
        self.assertEqual(flushed_count, 1)
