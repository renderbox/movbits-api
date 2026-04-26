import datetime
from types import SimpleNamespace
from unittest.mock import patch

import stripe
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.test import override_settings
from django.urls import resolve, reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from vendor.models import CustomerProfile, Invoice
from vendor.models.choice import InvoiceStatus

from billing.api.views import OneClickPurchaseView
from billing.models import Product
from wallet.models import CreditTypes, Wallet

User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False)
class CreatePaymentIntentWithAuthTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="pass1234")
        self.site = Site.objects.get_current()
        self.profile = CustomerProfile.objects.create(user=self.user, site=self.site)
        self.invoice = self.profile.get_cart()
        # Create an order item that costs $15 (1500 cents)
        self.product = Product.objects.create(
            name="Test Product",
            description={},
            available=True,
            site=self.site,
            product_type=Product.ProductType.CREDIT_PACKAGE,
        )
        self.offer = self.product.offers.create(
            name="Test Product Offer",
            available=True,
            start_date=timezone.now() - datetime.timedelta(days=1),
            end_date=None,
        )
        self.price = self.offer.prices.create(
            cost=1500,  # $15.00
            currency="usd",
            start_date=timezone.now() - datetime.timedelta(days=1),
            end_date=None,
            priority=1,
        )
        self.invoice.add_offer(self.offer)
        self.invoice.update_totals()

        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    @patch("billing.api.views.stripe.PaymentIntent.create")
    def test_authenticated_user_creates_payment_intent(self, mock_create):
        mock_create.return_value = SimpleNamespace(
            id="pi_test_123",
            client_secret="secret_abc123",
        )

        url = reverse("billing-create-payment-intent")
        data = {"amount": 1500, "currency": "usd"}
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertIn("clientSecret", response.data)
        self.assertEqual(response.data["clientSecret"], "secret_abc123")

        mock_create.assert_called_once_with(
            amount=1500,
            currency="usd",
            automatic_payment_methods={"enabled": True},
            metadata={
                "invoice_id": str(self.invoice.pk),
                "user_id": str(self.user.pk),
                "profile_id": str(self.profile.pk),
                "opening_balance": "0",
            },
        )

    def test_unauthenticated_request_fails_or_sets_anonymous_metadata(self):
        url = reverse("billing-create-payment-intent")
        self.client.credentials()
        response = self.client.post(
            url, {"amount": 1500, "currency": "usd"}, format="json"
        )

        # Depending on your view, adjust expected behavior
        self.assertEqual(response.status_code, 401)  # auth required
        # You can assert anonymous metadata if applicable

    def test_missing_currency_returns_400(self):
        url = reverse("billing-create-payment-intent")
        response = self.client.post(url, {"amount": 1500}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("currency", response.data)

    def test_missing_amount_returns_400(self):
        url = reverse("billing-create-payment-intent")
        response = self.client.post(url, {"currency": "usd"}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("amount", response.data)

    def test_amount_currency_mismatch_returns_400(self):
        url = reverse("billing-create-payment-intent")
        response = self.client.post(
            url, {"amount": 999, "currency": "usd"}, format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)

    @patch("billing.api.views.stripe.PaymentIntent.create")
    def test_currency_is_normalized_to_lowercase(self, mock_create):
        mock_create.return_value = SimpleNamespace(
            id="pi_test_456",
            client_secret="secret_def456",
        )
        url = reverse("billing-create-payment-intent")
        response = self.client.post(
            url, {"amount": 1500, "currency": "USD"}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("clientSecret", response.data)


@override_settings(SECURE_SSL_REDIRECT=False)
class OneClickPurchaseViewTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="oneclickuser", password="pass1234"
        )
        self.site = Site.objects.get_current()
        self.product = Product.objects.create(
            name="One Click Product",
            description={},
            available=True,
            site=self.site,
            product_type=Product.ProductType.CREDIT_PACKAGE,
        )
        self.offer = self.product.offers.create(
            name="One Click Offer",
            available=True,
            start_date=timezone.now() - datetime.timedelta(days=1),
            end_date=None,
        )
        self.offer.prices.create(
            cost=1500,
            currency="usd",
            start_date=timezone.now() - datetime.timedelta(days=1),
            end_date=None,
            priority=1,
        )

        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        self.url = reverse("billing_one_click_purchase")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    @patch("billing.api.views.stripe.PaymentIntent.create")
    def test_one_click_purchase_returns_client_secret(self, mock_create):
        mock_create.return_value = SimpleNamespace(
            id="pi_test_one_click",
            client_secret="secret_one_click",
        )

        response = self.client.post(
            self.url, {"offer_uuid": str(self.offer.uuid)}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data.keys()), {"clientSecret", "invoiceId"})
        self.assertEqual(response.data["clientSecret"], "secret_one_click")

        invoice = Invoice.objects.get(uuid=response.data["invoiceId"])
        wallet = Wallet.objects.get(
            user=self.user,
            site=self.site,
            credit_type=CreditTypes.CREDIT,
        )
        profile = self.user.customer_profile.get(site=self.site)

        self.assertEqual(invoice.profile, profile)
        self.assertEqual(invoice.status, InvoiceStatus.CHECKOUT)
        self.assertEqual(invoice.total, 1500)
        self.assertIsNotNone(invoice.ordered_date)
        self.assertEqual(
            invoice.vendor_notes["stripe_payment_intent_id"], "pi_test_one_click"
        )
        self.assertEqual(
            invoice.vendor_notes["stripe_client_secret"], "secret_one_click"
        )
        self.assertEqual(invoice.vendor_notes["expected_total"], 1500)
        self.assertEqual(invoice.vendor_notes["expected_currency"], "usd")
        self.assertEqual(
            invoice.vendor_notes["metadata"],
            {
                "invoice_id": str(invoice.uuid),
                "site_id": str(self.site.pk),
                "user_id": str(self.user.pk),
                "profile_id": str(profile.pk),
                "opening_credit_balance": str(wallet.balance),
                "product_name": self.product.name,
            },
        )

        mock_create.assert_called_once_with(
            amount=1500,
            currency="usd",
            automatic_payment_methods={"enabled": True},
            metadata=invoice.vendor_notes["metadata"],
        )

    def test_one_click_purchase_missing_offer_uuid_returns_400(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"detail": "Missing offer_uuid."})

    def test_one_click_purchase_unknown_offer_returns_404(self):
        response = self.client.post(
            self.url,
            {"offer_uuid": "00000000-0000-0000-0000-000000000000"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"detail": "Offer not found."})

    @patch("billing.api.views.stripe.PaymentIntent.create")
    def test_one_click_purchase_stripe_error_returns_400(self, mock_create):
        mock_create.side_effect = stripe.error.InvalidRequestError(
            message="bad request",
            param="offer_uuid",
        )

        response = self.client.post(
            self.url, {"offer_uuid": str(self.offer.uuid)}, format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)

    @patch("billing.api.views.stripe.PaymentIntent.create")
    def test_one_click_purchase_accepts_product_offer_id_alias(self, mock_create):
        mock_create.return_value = SimpleNamespace(
            id="pi_test_alias",
            client_secret="secret_alias",
        )

        response = self.client.post(
            self.url, {"productOfferId": str(self.offer.uuid)}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["clientSecret"], "secret_alias")
        self.assertTrue(
            Invoice.objects.filter(uuid=response.data["invoiceId"]).exists()
        )

    def test_one_click_purchase_endpoint_resolves_to_expected_view(self):
        self.assertEqual(self.url, "/api/v1/billing/one-click")
        match = resolve(self.url)
        self.assertEqual(match.view_name, "billing_one_click_purchase")
        self.assertIs(match.func.view_class, OneClickPurchaseView)


@override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False)
class CartApiTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="cartuser", password="pass1234")
        self.site = Site.objects.get_current()
        self.product = Product.objects.create(
            name="Test Credits",
            description={},
            available=True,
            site=self.site,
            product_type=Product.ProductType.CREDIT_PACKAGE,
        )
        self.offer = self.product.offers.create(
            name="Test Credits Offer",
            available=True,
            start_date=timezone.now() - datetime.timedelta(days=1),
            end_date=None,
        )
        self.offer.prices.create(
            cost=1500,
            currency="usd",
            start_date=timezone.now() - datetime.timedelta(days=1),
            end_date=None,
            priority=1,
        )
        self.product_two = Product.objects.create(
            name="Test Credits Two",
            description={},
            available=True,
            site=self.site,
            product_type=Product.ProductType.CREDIT_PACKAGE,
        )
        self.offer_two = self.product_two.offers.create(
            name="Test Credits Offer Two",
            available=True,
            start_date=timezone.now() - datetime.timedelta(days=1),
            end_date=None,
        )
        self.offer_two.prices.create(
            cost=2500,
            currency="usd",
            start_date=timezone.now() - datetime.timedelta(days=1),
            end_date=None,
            priority=1,
        )

        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    def test_cart_get_add_and_remove(self):
        url = reverse("billing-edit-cart")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("order_items", response.data)
        self.assertEqual(len(response.data["order_items"]), 0)

        response = self.client.post(
            url, {"uuid": str(self.product.uuid)}, format="json"
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            url, {"uuid": str(self.product_two.uuid)}, format="json"
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("order_items", response.data)
        self.assertEqual(len(response.data["order_items"]), 2)

        response = self.client.patch(
            url,
            {"uuid": str(self.offer.uuid), "quantity": 2},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("line_items", response.data)
        self.assertGreaterEqual(len(response.data["line_items"]), 2)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("order_items", response.data)
        self.assertEqual(len(response.data["order_items"]), 2)

        response = self.client.patch(
            url,
            {"uuid": str(self.offer.uuid), "quantity": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("line_items", response.data)
        self.assertGreaterEqual(len(response.data["line_items"]), 2)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("order_items", response.data)
        self.assertEqual(len(response.data["order_items"]), 2)

        response = self.client.delete(
            url,
            {"uuid": str(self.product.uuid)},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("line_items", response.data)
        self.assertEqual(len(response.data["line_items"]), 1)


@override_settings(SECURE_SSL_REDIRECT=False)
class CreditPackageListViewTests(APITestCase):

    def setUp(self):
        self.site = Site.objects.get_current()
        self.product = Product.objects.create(
            name="Offerless Credits",
            description={},
            available=True,
            site=self.site,
            product_type=Product.ProductType.CREDIT_PACKAGE,
        )

    def test_list_handles_product_without_offer(self):
        url = reverse("billing-credit-packages")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
