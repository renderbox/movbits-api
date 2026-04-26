from django.test import TestCase
from django.urls import reverse


class CoreAppTests(TestCase):
    def test_home_page_loads(self):
        """Test that the home page loads successfully."""
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 302)

        # lets make sure the redirect is to the movbits page
        self.assertEqual(response.url, "https://www.movbits.com")
