from django.test import TestCase

from event_machine.models import LogBlock


class LogBlockModelTests(TestCase):
    """
    Test cases for the LogBlock model.
    """

    def test_create_log_block(self):
        """
        Test creating a LogBlock instance.
        """
        log_block = LogBlock.objects.create(
            group="test_group",
            time_block="20230530T1200",
            log_data=[{"key": "value"}],
            statistics={},  # Provide default value for statistics
        )
        self.assertEqual(log_block.group, "test_group")
        self.assertEqual(log_block.time_block, "20230530T1200")
        self.assertEqual(log_block.log_data, [{"key": "value"}])
