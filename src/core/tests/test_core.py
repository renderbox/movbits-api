# # Moved from tests.py

# import pytest
# from django.test import Client, TestCase
# from django.urls import reverse

# class CoreAppTests(TestCase):
#     def test_home_page_loads(self):
#         """Test that the home page loads successfully."""
#         response = self.client.get(reverse("core:home"))
#         self.assertEqual(response.status_code, 200)
#         self.assertTemplateUsed(response, "core/home.html")

#     def test_about_page_loads(self):
#         """Test that the about page loads successfully."""
#         response = self.client.get(reverse("core:about"))
#         self.assertEqual(response.status_code, 200)
#         self.assertTemplateUsed(response, "core/about.html")


# @pytest.mark.django_db
# def test_views_status_code():
#     """Test that the core app views return a 200 status code by default."""
#     client = Client()
#     base_catalog_urls = [
#         reverse("core:home"),
#     ]

#     for url in base_catalog_urls:
#         response = client.get(url)
#         assert response.status_code == 200
