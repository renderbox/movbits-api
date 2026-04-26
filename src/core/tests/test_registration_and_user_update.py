import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.api.serializers import RegisterSerializer

User = get_user_model()


@pytest.mark.django_db
def test_register_requires_agree_to_terms():
    data = {
        "email": "test@example.com",
        "password": "s3cret123",
        "confirmPassword": "s3cret123",
        "agreeToTerms": False,
    }
    serializer = RegisterSerializer(data=data)
    assert not serializer.is_valid()
    assert "agreeToTerms" in serializer.errors
    assert "Accepting the terms is required." in serializer.errors["agreeToTerms"][0]


@pytest.mark.django_db
def test_register_duplicate_username_rejected():
    User.objects.create_user(
        email="existing@example.com", password="pass", username="taken"
    )
    data = {
        "email": "new@example.com",
        "password": "s3cret123",
        "confirmPassword": "s3cret123",
        "agreeToTerms": True,
        "username": "taken",
    }
    serializer = RegisterSerializer(data=data)
    assert not serializer.is_valid()
    assert "username" in serializer.errors


@pytest.mark.django_db
def test_current_user_patch_updates_names_and_username():
    client = APIClient()
    user = User.objects.create_user(
        email="user@example.com",
        password="s3cret123",
        username="oldname",
        first_name="Old",
        last_name="Name",
    )
    client.force_authenticate(user=user)

    resp = client.patch(
        "/api/v1/user/me",
        {
            "firstName": "New",
            "lastName": "Name",
            "username": "newname",
        },
        format="json",
    )
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.first_name == "New"
    assert user.last_name == "Name"
    assert user.username == "newname"


@pytest.mark.django_db
def test_current_user_patch_rejects_duplicate_username():
    User.objects.create_user(
        email="other@example.com", password="pass", username="taken"
    )
    client = APIClient()
    user = User.objects.create_user(
        email="user@example.com", password="s3cret123", username="original"
    )
    client.force_authenticate(user=user)

    resp = client.patch(
        "/api/v1/user/me",
        {
            "username": "taken",
        },
        format="json",
    )
    assert resp.status_code == 400
    assert "username" in resp.data
