# import pytest
# from django.test import Client
# from django.urls import reverse


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
