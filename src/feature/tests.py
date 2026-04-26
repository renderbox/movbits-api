from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from feature.models import FeatureFlag

User = get_user_model()


@override_settings(ROOT_URLCONF="feature.api.urls")
class FeatureFlagAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = Site.objects.get_current()
        cls.other_site = Site.objects.create(domain="other.example", name="Other")

        cls.public_bool = FeatureFlag.objects.create(
            key="publicFeature",
            site=cls.site,
            active=True,
            value="true",
            type=FeatureFlag.TypeChoices.BOOLEAN,
        )
        cls.public_int = FeatureFlag.objects.create(
            key="publicCount",
            site=cls.site,
            active=True,
            value="7",
            type=FeatureFlag.TypeChoices.INTEGER,
        )
        cls.public_string = FeatureFlag.objects.create(
            key="publicLabel",
            site=cls.site,
            active=True,
            value="hello",
            type=FeatureFlag.TypeChoices.STRING,
        )
        cls.inactive_flag = FeatureFlag.objects.create(
            key="inactiveFlag",
            site=cls.site,
            active=False,
            value="true",
            type=FeatureFlag.TypeChoices.BOOLEAN,
        )
        cls.other_site_flag = FeatureFlag.objects.create(
            key="otherSiteFlag",
            site=cls.other_site,
            active=True,
            value="true",
            type=FeatureFlag.TypeChoices.BOOLEAN,
        )

        content_type = ContentType.objects.get_for_model(FeatureFlag)
        cls.restricted_perm = Permission.objects.get(
            codename="can_beta_test_features", content_type=content_type
        )
        cls.restricted_flag = FeatureFlag.objects.create(
            key="restrictedFlag",
            site=cls.site,
            active=True,
            value="secret",
            type=FeatureFlag.TypeChoices.STRING,
        )
        cls.restricted_flag.permissions.add(cls.restricted_perm)

    def test_list_public_flags_and_value_casting(self):
        response = self.client.get(reverse("feature-flags-list"))

        self.assertEqual(response.status_code, 200)
        results = {item["key"]: item["value"] for item in response.data}

        self.assertIn(self.public_bool.key, results)
        self.assertIn(self.public_int.key, results)
        self.assertIn(self.public_string.key, results)
        self.assertNotIn(self.inactive_flag.key, results)
        self.assertNotIn(self.other_site_flag.key, results)
        self.assertNotIn(self.restricted_flag.key, results)

        self.assertIs(results[self.public_bool.key], True)
        self.assertEqual(results[self.public_int.key], 7)
        self.assertEqual(results[self.public_string.key], "hello")

    def test_authenticated_user_without_permission_cannot_see_restricted(self):
        user = User.objects.create_user(username="noperms", password="pass1234")
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("feature-flags-list"))

        self.assertEqual(response.status_code, 200)
        results = {item["key"]: item["value"] for item in response.data}
        self.assertNotIn(self.restricted_flag.key, results)

    def test_authenticated_user_with_permission_sees_restricted(self):
        user = User.objects.create_user(username="withperms", password="pass1234")
        user.user_permissions.add(self.restricted_perm)
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("feature-flags-list"))

        self.assertEqual(response.status_code, 200)
        results = {item["key"]: item["value"] for item in response.data}
        self.assertIn(self.restricted_flag.key, results)
