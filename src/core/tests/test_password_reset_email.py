from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


class PasswordResetEmailTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="reset@example.com",
            password="pass123",
            username="resetuser",
        )

    def _request_password_reset(self):
        mail.outbox.clear()
        response = self.client.post(
            reverse("rest_password_reset"), {"email": self.user.email}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        return mail.outbox[0].body

    @override_settings(
        DEVELOPMENT_MODE=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_password_reset_email_uses_localhost_link_in_development(self):
        body = self._request_password_reset()
        self.assertIn("http://localhost:3000/reset-password?uid=", body)

    @override_settings(
        DEVELOPMENT_MODE=False,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_password_reset_email_uses_production_link(self):
        body = self._request_password_reset()
        self.assertIn("https://www.movbits.com/reset-password?uid=", body)
