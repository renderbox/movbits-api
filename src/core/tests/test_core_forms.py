from django.test import TestCase

from core.forms import ProfileForm


class FormTests(TestCase):
    def test_profile_form_valid(self):
        """Test that the ProfileForm validates correctly."""
        form = ProfileForm(
            data={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "date_of_birth": "1990-01-01",
            }
        )
        self.assertTrue(form.is_valid())

    def test_profile_form_invalid(self):
        """Test that the ProfileForm handles invalid data."""
        form = ProfileForm(
            data={
                "first_name": "",
                "last_name": "",
                "email": "invalid-email",
                "date_of_birth": "",
            }
        )
        self.assertFalse(form.is_valid())
