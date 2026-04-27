from datetime import date

from django.test import TestCase
from django.utils import timezone

from core.models import MBUser


class ModelTests(TestCase):
    def test_story_user_age_property(self):
        """Test the age property of the MBUser model."""
        date_of_birth = date(1990, 1, 1)
        user = MBUser.objects.create(
            username="testuser",
            date_of_birth=date_of_birth,  # Pass a proper datetime.date object
        )
        today = timezone.now().date()
        expected_age = today.year - date_of_birth.year
        if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
            expected_age -= 1
        self.assertEqual(user.age, expected_age)
