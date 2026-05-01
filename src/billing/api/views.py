import logging

import stripe
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.timezone import now as tz_now
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from vendor.models import Invoice, Offer
from vendor.models.choice import InvoiceStatus
from vendor.utils import get_site_from_request

from events.emit import TOPIC_PURCHASES, emit
from events.schemas import CreditPurchasedEvent
from wallet.models import CreditTypes, Wallet, WalletTransaction  # noqa: E501

from ..models import Product  # CreditPackage, Receipt, Wallet
from .serializers import (  # VendorInvoiceSerializer,
    CartSerializer,
    CreatePaymentIntentSerializer,
    CreditCartSerializer,
    CreditPackageSerializer,
)

stripe.api_key = settings.STRIPE_SECRET_KEY


def _get_or_create_stripe_customer(user):
    """
    Return the Stripe customer ID for the given user, creating one if absent.
    Saves the new ID back to the user record on success.
    Returns None if creation fails, so callers can fall back gracefully.
    """
    if user.stripe_customer_id:
        return user.stripe_customer_id

    try:
        customer = stripe.Customer.create(
            email=user.email,
            metadata={"user_id": str(user.pk)},
        )
        user.stripe_customer_id = customer.id
        user.save(update_fields=["stripe_customer_id"])
        stripe_logger.info(
            "Stripe customer created",
            extra={
                "event": "stripe_customer_created",
                "user_id": user.pk,
                "stripe_customer_id": customer.id,
            },
        )
        return customer.id
    except stripe.StripeError as e:
        logger.warning(f"Could not create Stripe customer for user {user.pk}: {e}")
        return None


# Simple in-memory mock state (per-process, dev only)
PAYMENT_METHODS = {}
USER_BALANCES = {}
REFUNDS = {}

logger = logging.getLogger(__name__)
stripe_logger = logging.getLogger("stripe")
vendor_logger = logging.getLogger("vendor")


# def now_iso():
#     return datetime.datetime.utcnow().isoformat() + "Z"


# # --- Helpers to create mock objects ----------------------------------------
# def make_credit_package(idx=1):
#     pid = str(uuid.uuid4())
#     return {
#         "id": pid,
#         "name": f"{idx * 100} Credits",
#         "credits": idx * 100,
#         "price": round(0.01 * idx * 100, 2),
#         "bonusCredits": 10 if idx % 2 == 0 else 0,
#         "popular": idx == 2,
#     }


# def make_subscription(plan="free"):
#     return {
#         "id": str(uuid.uuid4()),
#         "userId": str(uuid.uuid4()),
#         "plan": plan,
#         "status": "active" if plan != "free" else "trial",
#         "startDate": now_iso(),
#         "endDate": (
#             datetime.datetime.utcnow() + datetime.timedelta(days=30)
#         ).isoformat()
#         + "Z",
#         "autoRenew": True if plan != "free" else False,
#         "price": 9.99 if plan == "premium" else 19.99 if plan == "pro" else 0.0,
#     }


# def make_billing_history_item(idx=1):
#     tid = str(uuid.uuid4())
#     return {
#         "id": tid,
#         "date": now_iso(),
#         "description": f"Purchase {idx}",
#         "amount": round(random.uniform(1, 50), 2),
#         "status": random.choice(["paid", "pending", "failed"]),
#         "invoiceUrl": f"https://example.com/invoices/{tid}.pdf",
#     }


# # --- Endpoints --------------------------------------------------------------


# @api_view(["GET"])
# def credit_packages(request):
#     packages = [make_credit_package(i) for i in range(1, 5)]
#     return Response(packages)


class CreditPackageListView(APIView):
    """List available credit packages."""

    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        now = timezone.now()
        credit_packages = (
            Offer.objects.filter(
                site=request.site,
                available=True,
                products__site=request.site,
                products__available=True,
                products__product_type=Product.ProductType.CREDIT_PACKAGE,
                start_date__lte=now,
            )
            .filter(Q(end_date__isnull=True) | Q(end_date__gte=now))
            .prefetch_related("products", "prices")
            .distinct()
        )
        serializer = CreditPackageSerializer(
            credit_packages, many=True, context={"now": now}
        )
        return Response(serializer.data)


class CartView(APIView):
    """endpoint to manage the user's cart, which is represented by an active Invoice linked to their CustomerProfile. GET returns the current cart state, POST adds an item to the cart, PATCH updates an item's quantity, and DELETE removes an item from the cart based on a provided item UUID. The cart is automatically created if it doesn't exist when adding items. This allows us to manage multiple items in a single transaction and ensure we have an accurate representation of the user's intended purchase before they proceed to payment."""  # noqa: E501

    # permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """Returns the current state of the user's cart, including items and totals."""
        if settings.DEBUG:
            user_model = get_user_model()
            user = user_model.objects.filter(id=1).first()
        else:
            user = request.user

        vendor_logger.info(
            f"CartView GET called by user {user.id} at site {request.site.id}"
        )

        profile, _ = user.customer_profile.get_or_create(site=request.site)
        cart = profile.get_cart()
        cart.update_totals()  # ensure totals are up to date before returning
        serializer = CartSerializer(cart)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):

        # This will be consistent so no need to check multiple field names.
        item_uuid = request.data.get("uuid")
        cart_id = request.data.get(
            "cart_id"
        )  # optional, for future use if we want to support multiple carts

        vendor_logger.info(
            f"CartView POST called with item_uuid={item_uuid} by user {request.user.id} at site {request.site.id}"
        )

        if not item_uuid:
            return Response(
                {"detail": "Missing item uuid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        site = get_site_from_request(request)
        try:
            product = Product.objects.get(
                uuid=item_uuid,
                site=site,
                available=True,
                product_type=Product.ProductType.CREDIT_PACKAGE,
            )
        except Product.DoesNotExist:
            return Response(
                {"detail": "Item not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        offer = product.get_current_offer()
        if offer is None:
            return Response(
                {"detail": "Item is not currently available."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile, _ = request.user.customer_profile.get_or_create(
            site=site
        )  # Make sure the user has a profile for this site

        # Use cart_id if provided; otherwise get or create the latest active cart for the user.

        if cart_id:
            cart = Invoice.objects.filter(
                id=cart_id, profile=profile, status=InvoiceStatus.ACTIVE
            ).first()
        else:
            cart = (
                profile.get_cart()
            )  # Get or create an active cart (Invoice) for the user
            # This can return multiple carts if the user has multiple active invoices, so we need to filter by status
            # and get the latest one.

        items = None
        for name in ("order_items", "line_items", "items", "lines", "cart_items"):
            value = getattr(cart, name, None)
            if value is None:
                continue
            items = value
            break

        updated_quantity = False
        existing_item = None
        if items is not None and hasattr(items, "filter"):
            existing_item = items.filter(offer=offer).first()
            if existing_item is None:
                offer_id = getattr(offer, "id", None) or getattr(offer, "pk", None)
                if offer_id is not None:
                    existing_item = items.filter(offer_id=offer_id).first()
        elif items is not None:
            for candidate in items:
                candidate_offer = getattr(candidate, "offer", None)
                if candidate_offer == offer:
                    existing_item = candidate
                    break
                if str(getattr(candidate_offer, "id", "")) == str(
                    getattr(offer, "id", "")
                ):
                    existing_item = candidate
                    break
                if str(getattr(candidate_offer, "uuid", "")) == str(
                    getattr(offer, "uuid", "")
                ):
                    existing_item = candidate
                    break

        if existing_item is not None:
            for field in ("quantity", "qty", "count"):
                if hasattr(existing_item, field):
                    current_value = getattr(existing_item, field) or 0
                    setattr(existing_item, field, current_value + 1)
                    try:
                        existing_item.save(update_fields=[field])
                    except Exception:
                        existing_item.save()
                    updated_quantity = True
                    break

            if updated_quantity:
                for name in (
                    "update_totals",
                    "recalculate_totals",
                    "calculate_totals",
                    "recalculate",
                    "refresh_totals",
                    "update_total",
                    "calculate_total",
                ):
                    method = getattr(cart, name, None)
                    if callable(method):
                        try:
                            method()
                        except TypeError:
                            continue
                        break
                else:
                    try:
                        cart.save()
                    except Exception:
                        pass

        if not updated_quantity:
            cart.add_offer(
                offer
            )  # Add the offer to the cart (Invoice), which creates an InvoiceItem and updates totals

        # Print the items in the cart for debugging
        # vendor_logger.info(f"Cart items count: {cart.order_items.count()}")

        serializer = CreditCartSerializer(cart)
        # vendor_logger.info(f"Cart serialized data: {serializer.data}")
        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        item_uuid = request.data.get("uuid")
        quantity = request.data.get("quantity")

        vendor_logger.info(
            f"CartView PATCH called with item_uuid={item_uuid} quantity={quantity} "
            f"by user {request.user.id} at site {request.site.id}"
        )

        if not item_uuid:
            return Response(
                {"detail": "Missing item uuid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if quantity is None:
            return Response(
                {"detail": "Missing quantity."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response(
                {"detail": "Quantity must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        site = get_site_from_request(request)
        profile, _ = request.user.customer_profile.get_or_create(site=site)
        cart = profile.get_cart()

        try:
            offer = Offer.objects.get(uuid=item_uuid, site=site)
        except Offer.DoesNotExist:
            return Response(
                {"detail": "Offer not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        items = None
        for name in ("order_items", "line_items", "items", "lines", "cart_items"):
            value = getattr(cart, name, None)
            if value is None:
                continue
            items = value
            break

        existing_item = None
        if items is not None and hasattr(items, "filter"):
            existing_item = items.filter(offer=offer).first()
            if existing_item is None:
                offer_id = getattr(offer, "id", None) or getattr(offer, "pk", None)
                if offer_id is not None:
                    existing_item = items.filter(offer_id=offer_id).first()
        elif items is not None:
            for candidate in items:
                candidate_offer = getattr(candidate, "offer", None)
                if candidate_offer == offer:
                    existing_item = candidate
                    break
                if str(getattr(candidate_offer, "id", "")) == str(
                    getattr(offer, "id", "")
                ):
                    existing_item = candidate
                    break
                if str(getattr(candidate_offer, "uuid", "")) == str(
                    getattr(offer, "uuid", "")
                ):
                    existing_item = candidate
                    break

        if existing_item is None:
            return Response(
                {"detail": "Item not found in cart."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if quantity <= 0:
            cart.remove_offer(offer, clear=True)
        else:
            updated_quantity = False
            for field in ("quantity", "qty", "count"):
                if hasattr(existing_item, field):
                    setattr(existing_item, field, quantity)
                    try:
                        existing_item.save(update_fields=[field])
                    except Exception:
                        existing_item.save()
                    updated_quantity = True
                    break

            if not updated_quantity:
                return Response(
                    {"detail": "Item quantity field not found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        for name in (
            "update_totals",
            "recalculate_totals",
            "calculate_totals",
            "recalculate",
            "refresh_totals",
            "update_total",
            "calculate_total",
        ):
            method = getattr(cart, name, None)
            if callable(method):
                try:
                    method()
                except TypeError:
                    continue
                break
        else:
            try:
                cart.save()
            except Exception:
                pass

        try:
            cart.refresh_from_db()
        except Exception:
            pass

        serializer = CreditCartSerializer(cart)
        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        item_uuid = request.data.get("uuid")

        vendor_logger.info(
            f"CartView DELETE called with item_uuid={item_uuid} "
            f"by user {request.user.id} at site {request.site.id} with data: {request.data}"
        )

        if not item_uuid:
            return Response(
                {"detail": "Missing item uuid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        site = get_site_from_request(request)
        profile, _ = request.user.customer_profile.get_or_create(site=site)
        cart = profile.get_cart()

        try:
            offer = Offer.objects.get(uuid=item_uuid)
        except Offer.DoesNotExist:
            product = Product.objects.filter(uuid=item_uuid, site=site).first()
            if product is None:
                return Response(
                    {"detail": "Offer not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            offer = product.get_current_offer()
            if offer is None:
                return Response(
                    {"detail": "Item is not currently available."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        cart.remove_offer(offer)

        for name in (
            "update_totals",
            "recalculate_totals",
            "calculate_totals",
            "recalculate",
            "refresh_totals",
            "update_total",
            "calculate_total",
        ):
            method = getattr(cart, name, None)
            if callable(method):
                try:
                    method()
                except TypeError:
                    continue
                break
        else:
            try:
                cart.save()
            except Exception:
                pass

        try:
            cart.refresh_from_db()
        except Exception:
            pass

        serializer = CreditCartSerializer(cart)
        return Response(serializer.data)


class CreatePaymentIntentView(APIView):
    """Create a Stripe Payment Intent for purchasing credits."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):

        vendor_logger.info(
            f"CreatePaymentIntentView POST called by user {request.user.id} "
            f"at site {request.site.id} with data: {request.data}"
        )

        # TODO: Check if the user has a Stripe ID on their profile and create one if not.

        serializer = CreatePaymentIntentSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        # vendor_logger.info(f"Payment intent serializer validated data: {serializer.validated_data}")

        # If the serializer is valid, it means the cart and profile are valid and we can trust
        # the expected total and currency it provides (which are calculated based on the actual
        # cart contents and offers, not user input). This prevents tampering with the amount on
        # the client side.
        expected_total = serializer.validated_data["amount"]
        expected_currency = serializer.validated_data["currency"]

        profile, created = request.user.customer_profile.get_or_create(
            site=request.site
        )
        # vendor_logger.info(
        #     f"Customer profile for user {request.user.id} at site {request.site.id}: {profile}, created: {created}"
        # )

        if created:
            vendor_logger.info(
                f"Created new customer profile for user {request.user.id} "
                f"at site {request.site.id} during payment intent creation."
            )
            # TODO: log this in a more structured way or create an audit record if needed.

        cart = profile.get_cart()

        # Print the cart

        # fail fast on an empty cart
        has_items = False
        if cart is not None:
            for name in ("order_items", "line_items", "items", "lines", "cart_items"):
                value = getattr(cart, name, None)
                if value is None:
                    continue
                if hasattr(value, "exists"):
                    has_items = value.exists()
                else:
                    has_items = bool(value)
                break
        if cart is None or not has_items:
            return Response(
                {"detail": "Cart is empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart.update_totals()  # make sure we have the latest totals
        cart_total = cart.total
        cart_currency = cart.currency

        vendor_logger.info(
            f"Cart total: {cart_total} {cart_currency}, expected: {expected_total} {expected_currency}"
        )

        # Defensive: cart should always have totals, but guard and log if not.
        if cart_total is None or cart_currency is None:
            return Response(
                {"detail": "Cart total is unavailable."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            cart_total = int(cart_total)
        except (TypeError, ValueError):
            return Response(
                {"detail": "Cart total is unavailable."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            cart_total != expected_total
            or str(cart_currency).lower() != expected_currency
        ):
            return Response(
                {"detail": "Cart total does not match the expected amount."},
                status=status.HTTP_409_CONFLICT,
            )

        # lets create the metadata for the payment intent which will help us identify the correct cart and user when we receive the webhook from Stripe after payment is completed. This is crucial for updating the correct records based on the actual cart contents and ensuring we credit the correct user.  # noqa: E501
        wallet, _ = Wallet.objects.get_or_create(
            user=request.user, site=request.site, credit_type=CreditTypes.CREDIT
        )
        metadata = {
            "invoice_id": str(
                cart.pk
            ),  # there will always be an ID when the cart/invoice is saved
            "user_id": str(request.user.pk),  # a user's ID is required on the site
            "profile_id": str(profile.pk),
            "opening_balance": str(wallet.balance),
        }

        stripe_customer_id = _get_or_create_stripe_customer(request.user)
        intent_kwargs = dict(
            amount=expected_total,
            currency=expected_currency,
            automatic_payment_methods={"enabled": True},
            metadata=metadata,
        )
        if stripe_customer_id:
            intent_kwargs["customer"] = stripe_customer_id

        try:
            payment_intent = stripe.PaymentIntent.create(**intent_kwargs)
            stripe_logger.info(
                "Payment intent created",
                extra={
                    "event": "payment_intent_created",
                    "payment_intent_id": payment_intent.id,
                    "invoice_id": cart.pk,
                    "currency": expected_currency.lower(),
                    "amount_minor": int(expected_total),
                },
            )

            # update the invoice status and save the payment intent ID for later reference (e.g. in the webhook)
            cart.status = InvoiceStatus.CHECKOUT
            cart.save()
            # log the intent ID
            # cart.log_transaction(
            #     title="Payment Intent Created",
            #     message=f"Stripe PaymentIntent {payment_intent.id} created "
            #             f"with amount {expected_total} {expected_currency}.",
            # )

            return Response({"clientSecret": payment_intent.client_secret})
        except stripe.StripeError as e:
            # log and responde if a stripe error occurs during the payment intent creation.
            logger.error(f"Stripe error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class OneClickPurchaseView(APIView):
    """
    Create a Stripe PaymentIntent for a one-click offer purchase.

    Authentication:
    - Requires an authenticated user.

    Input (POST JSON):
    - offer_uuid (str, required): UUID of an Offer on the current site.

    Success response (200):
    - {"clientSecret": "<stripe_payment_intent_client_secret>", "invoiceId": "<invoice_uuid>"}

    Error responses:
    - 400: {"detail": "Missing offer_uuid."} when offer_uuid is not provided.
    - 404: {"detail": "Offer not found."} when the offer does not exist on the site.
    - 400: {"error": "<stripe_error_message>"} when Stripe intent creation fails.

    Side effects:
    - Creates a Wallet for the user/site/credit type if one does not already exist.
    - Creates a customer profile for the user/site if one does not already exist.
    - Creates an Invoice in CHECKOUT status and uses its UUID in Stripe metadata.
    - Creates a Stripe PaymentIntent and logs related billing/Stripe events.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):

        offer_uuid = request.data.get("offer_uuid") or request.data.get(
            "productOfferId"
        )
        if not offer_uuid:
            vendor_logger.info(
                f"OneClickPurchaseView POST called by user {request.user.id} "
                f"at site {request.site.id} with data: {request.data}, BAD REQUEST"
            )
            return Response(
                {"detail": "Missing offer_uuid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        offer = Offer.objects.filter(uuid=offer_uuid, site=request.site).first()
        if not offer:
            return Response(
                {"detail": "Offer not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        wallet, _ = Wallet.objects.get_or_create(
            user=request.user, site=request.site, credit_type=CreditTypes.CREDIT
        )

        profile, _ = request.user.customer_profile.get_or_create(site=request.site)

        # Special invoice for single item purchase.
        cart = Invoice.objects.create(
            profile=profile, status=InvoiceStatus.CHECKOUT
        )  # Unless there is a new state, this goes right to "CHECKOUT"

        cart.add_offer(
            offer
        )  # Add the offer to the cart (Invoice), which creates an InvoiceItem and updates totals

        # Set order date so we can track when the one-click purchase was initiated.
        cart.ordered_date = timezone.now()

        offer_product = offer.products.first() if hasattr(offer, "products") else None

        metadata = {
            "invoice_id": str(
                cart.uuid
            ),  # there will always be an ID when the cart/invoice is saved
            "site_id": str(request.site.pk),
            "user_id": str(request.user.pk),  # a user's ID is required on the site
            "profile_id": str(profile.pk),
            "opening_credit_balance": str(wallet.balance),
            "product_name": str(getattr(offer_product, "name", "")),
        }

        # TODO: Derive the expected currency from the offer's active price when
        # available, otherwise fall back to the offer currency or a sane default.
        # Stripe requires an explicit matching currency for the payment intent.
        price_obj = (
            offer.get_current_price_object()
            if hasattr(offer, "get_current_price_object")
            else None
        )
        expected_currency = (
            getattr(price_obj, "currency", None)
            or getattr(offer, "currency", None)
            or (
                offer.get_real_currency_display()
                if hasattr(offer, "get_real_currency_display")
                else None
            )
            or "usd"
        )
        expected_currency = str(expected_currency).lower()

        # Calculate taxes before creating the payment intent — Stripe expects the final total.
        # cart.calculate_taxes()

        stripe_customer_id = _get_or_create_stripe_customer(request.user)
        intent_kwargs = dict(
            amount=int(cart.total),
            currency=expected_currency,
            automatic_payment_methods={"enabled": True},
            metadata=metadata,
        )
        if stripe_customer_id:
            intent_kwargs["customer"] = stripe_customer_id

        try:
            payment_intent = stripe.PaymentIntent.create(**intent_kwargs)
            # stripe_logger.info(
            #     "Payment intent created",
            #     extra={
            #         "event": "payment_intent_created",
            #         "payment_intent_id": payment_intent.id,
            #         "invoice_id": cart.pk,
            #         "currency": expected_currency.lower(),
            #         "amount_minor": int(cart.total),
            #     },
            # )

            # update the invoice status and save the payment intent ID for later reference (e.g. in the webhook)
            cart.status = InvoiceStatus.CHECKOUT

            # add in the transaction info into the Vendor Notes field on the invoice for later reference.
            # This is useful for debugging and tracking the purchase in the webhook.  Use JSON formatting.
            cart.vendor_notes = {
                "stripe_payment_intent_id": payment_intent.id,
                "stripe_client_secret": payment_intent.client_secret,
                "expected_total": cart.total,  # in cents, as Stripe expects
                "expected_currency": expected_currency,
                "metadata": metadata,
            }

            cart.save()

            stripe_logger.info(
                "Payment intent client secret returned",
                extra={
                    "event": "payment_intent_client_secret_returned",
                    "payment_intent_id": payment_intent.id,
                    "invoice_id": cart.pk,
                    "currency": expected_currency.lower(),
                    "amount_minor": cart.total,
                },
            )

            logger.info(
                "Payment intent client secret returned",
                extra={
                    "event": "payment_intent_client_secret_returned",
                    "payment_intent_id": payment_intent.id,
                    "invoice_id": cart.pk,
                    "currency": expected_currency.lower(),
                    "amount_minor": cart.total,
                },
            )

        except stripe.StripeError as e:
            # log and responde if a stripe error occurs during the payment intent creation.
            logger.error(f"Stripe error: {e}")
            stripe_logger.warning(
                "Payment intent creation failed",
                extra={
                    "event": "payment_intent_creation_failed",
                    "invoice_id": cart.pk,
                    "currency": expected_currency.lower(),
                    "amount_minor": int(cart.total),
                    "error": str(e),
                },
            )

            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"clientSecret": payment_intent.client_secret, "invoiceId": str(cart.uuid)}
        )


class CustomerPortalView(APIView):
    """
    Create a Stripe Billing Portal session for the authenticated user.

    The caller supplies a return_url so the portal can redirect back to the
    correct page in the SPA after the user is done.

    POST body:
      - return_url (str, required): the SPA URL to return to after the portal

    Success response (200):
      - {"url": "<stripe_billing_portal_url>"}

    Error responses:
      - 400: user has no stripe_customer_id
      - 400: Stripe error
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user

        if not user.stripe_customer_id:
            return Response(
                {"detail": "No billing account found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return_url = request.data.get("return_url")
        if not return_url:
            return Response(
                {"detail": "return_url is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            session = stripe.billing_portal.Session.create(
                customer=user.stripe_customer_id,
                return_url=return_url,
            )
            stripe_logger.info(
                "Customer portal session created",
                extra={
                    "event": "customer_portal_session_created",
                    "user_id": user.pk,
                    "stripe_customer_id": user.stripe_customer_id,
                },
            )
            return Response({"url": session.url})
        except stripe.StripeError as e:
            logger.error(
                f"Stripe error creating portal session for user {user.pk}: {e}"
            )
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    # TODO: Keep wallet credit application in the webhook flow. The success view
    # should only report the projected post-payment balance and wait for Stripe's
    # confirmation before any balance mutation happens.
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        """
        Handle Stripe webhook events.

        Updates the wallet if successful and marks the receipt as confirmed.
        This is the only place where the wallet balance is updated because it
        runs after Stripe confirms the payment completed.
        PurchaseCreditsSuccessView only reports the projected new balance.
        """

        # Read raw body before any request.data access — DRF parsing consumes the
        # stream and sets _read_started=True, which causes Django's request.body
        # property to raise RawPostDataException if accessed afterwards.
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

        try:
            event = stripe.Webhook.construct_event(
                payload,
                sig_header,
                settings.STRIPE_WEBHOOK_SECRET,
            )
        except (ValueError, stripe.SignatureVerificationError) as e:
            logger.warning(f"Stripe webhook error: {e}")
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # log the incoming webhook for debugging (after signature is verified)
        stripe_logger.info(
            f"StripeWebhookView POST called with event: {event.get('type')}",
            extra={
                "event_type": event.get("type"),
                "event_id": event.get("id"),
                "service": "billing:StripeWebhookView",
            },
        )

        event_type = event["type"]

        if event_type == "payment_intent.succeeded":
            intent = event["data"]["object"]
            invoice_id = intent.get("metadata", {}).get("invoice_id")

            if not invoice_id:
                logger.warning("Missing invoice_id in Stripe metadata.")
                return Response(status=status.HTTP_400_BAD_REQUEST)

            try:
                with transaction.atomic():
                    invoice = (
                        Invoice.objects.select_related("profile__user", "profile__site")
                        .prefetch_related("order_items__offer__products")
                        .select_for_update()
                        .get(uuid=invoice_id)
                    )

                    # Idempotency check: if the webhook already processed this
                    # invoice, return 200 without applying credits again.
                    vendor_notes = invoice.vendor_notes or {}
                    if vendor_notes.get("webhook_processed"):
                        return Response(status=status.HTTP_200_OK)

                    # Calculate credits from the invoice's order items
                    credits_added = invoice.order_items.filter(
                        offer__products__product_type=Product.ProductType.CREDIT_PACKAGE
                    ).aggregate(
                        total_credits=Coalesce(
                            Sum(
                                F("quantity")
                                * (
                                    F("offer__products__credits")
                                    + F("offer__products__bonus")
                                )
                            ),
                            0,
                        )
                    )[
                        "total_credits"
                    ]

                    user = invoice.profile.user
                    site = invoice.profile.site

                    wallet, _ = Wallet.objects.get_or_create(
                        user=user, site=site, credit_type=CreditTypes.CREDIT
                    )
                    wallet.balance = F("balance") + credits_added
                    wallet.save(update_fields=["balance"])
                    wallet.refresh_from_db(fields=["balance"])

                    WalletTransaction.objects.create(
                        wallet=wallet,
                        amount=credits_added,
                        balance_after=wallet.balance,
                        transaction_type=WalletTransaction.TransactionType.CREDIT_PURCHASE,
                        reference_type="stripe_invoice",
                        reference_id=str(invoice.uuid),
                        stripe_payment_intent_id=intent["id"],
                        metadata={
                            "amount_received": intent.get("amount_received"),
                            "currency": intent.get("currency"),
                            "stripe_event_id": event["id"],
                        },
                    )

                    # Mark invoice as complete and record that the webhook ran
                    invoice.status = InvoiceStatus.COMPLETE
                    invoice.vendor_notes = {
                        **vendor_notes,
                        "webhook_processed": True,
                        "webhook_payment_intent_id": intent["id"],
                    }
                    invoice.save(update_fields=["status", "vendor_notes"])

                    # Capture values for the on_commit closures before the
                    # lambda captures the loop variable (defensive copy).
                    _event_id = event["id"]
                    _intent_id = intent["id"]
                    _invoice_id = str(invoice.uuid)
                    _user_id = user.pk
                    _site_id = site.pk
                    _amount = intent.get("amount_received") or 0
                    _currency = (intent.get("currency") or "usd").lower()
                    _credits = credits_added
                    _balance = wallet.balance
                    _stripe_customer = getattr(user, "stripe_customer_id", "") or ""

                    # Log and emit only after the transaction is durable.
                    def _on_commit():
                        stripe_logger.info(
                            "Stripe payment_intent.succeeded processed",
                            extra={
                                "stripe_event_id": _event_id,
                                "event_type": "payment_intent.succeeded",
                                "payment_intent_id": _intent_id,
                                "invoice_id": _invoice_id,
                                "user_id": _user_id,
                                "amount_received": _amount,
                                "currency": _currency,
                                "credits_added": _credits,
                            },
                        )
                        emit(
                            TOPIC_PURCHASES,
                            CreditPurchasedEvent(
                                user_id=str(_user_id),
                                site_id=str(_site_id),
                                stripe_customer_id=_stripe_customer,
                                invoice_id=_invoice_id,
                                stripe_payment_intent_id=_intent_id,
                                stripe_event_id=_event_id,
                                amount_paid_minor=int(_amount),
                                currency=_currency,
                                credits_purchased=_credits,
                                balance_after=_balance,
                            ),
                        )

                    transaction.on_commit(_on_commit)

            except Invoice.DoesNotExist:
                logger.error(f"Invoice {invoice_id} not found.")
                return Response(status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_200_OK)


# # --- Credit management -----------------------------------------------------

# @api_view(["POST"])
# def purchase_credits(request):
#     payload = request.data or {}
#     package_id = payload.get("packageId")  # noqa: F841
#     payment_method = payload.get("paymentMethod")  # noqa: F841
#     # For mock, pick credits from package id presence or default to 100
#     credits_added = 100
#     new_balance = USER_BALANCES.get("default", 0) + credits_added
#     USER_BALANCES["default"] = new_balance
#     transaction_id = f"tx_{uuid.uuid4()}"
#     return Response(
#         {
#             "success": True,
#             "creditsAdded": credits_added,
#             "newBalance": new_balance,
#             "transactionId": transaction_id,
#         }
#     )


class PurchaseCreditsSuccessView(APIView):
    """Confirms a credit purchase and returns the projected new balance.
    The actual wallet credit happens in the Stripe webhook after payment confirmation.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):

        # TODO: a cart ID should be returned as invoiceId

        site = get_site_from_request(request)
        profile, _ = request.user.customer_profile.get_or_create(
            site=site
        )  # makes sure the user has a profile.

        # TODO: if a invoiceId is returned, we should use that to get the cart first.
        if "invoiceId" in request.data:
            invoice_id = request.data["invoiceId"]
            cart = Invoice.objects.filter(
                uuid=invoice_id, profile=profile, status=InvoiceStatus.CHECKOUT
            ).first()
            if cart is None:
                return Response(
                    {"detail": "Invoice not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        else:
            cart = profile.get_cart()  # will create one if none exists.

        # The cart should always have a value after this point

        wallet, _ = Wallet.objects.get_or_create(
            user=request.user, site=site, credit_type=CreditTypes.CREDIT
        )
        opening_balance = wallet.balance

        cart.status = InvoiceStatus.COMPLETE
        cart.save(update_fields=["status"])

        # credits_added = 0
        # if cart is not None:
        #     credits_added = CreditCartSerializer(cart).get_total_credits(cart)

        credits_added = (
            cart.order_items.filter(
                offer__products__product_type=Product.ProductType.CREDIT_PACKAGE
            ).aggregate(
                total_credits=Coalesce(
                    Sum(
                        F("quantity")
                        * (F("offer__products__credits") + F("offer__products__bonus"))
                    ),
                    0,
                )
            )[
                "total_credits"
            ]
            if cart
            is not None  # TODO: the cart will never be None.  is this necessary?
            else 0
        )

        cart_id = str(cart.uuid) if cart is not None else None

        new_balance = wallet.balance + credits_added

        # Log the results
        stripe_logger.info(
            f"Credits purchased successfully, added {credits_added} credits "
            f"to user {request.user.id}, new balance: {new_balance}, cart ID: {cart_id}",
            extra={
                "success": True,
                "creditsAdded": credits_added,
                "newBalance": new_balance,
                "openingBalance": opening_balance,
                "cart_id": cart_id,
            },
        )

        return Response(
            {
                "success": True,
                "openingBalance": opening_balance,  # display only; wallet credited by webhook
                "creditsAdded": credits_added,
                "newBalance": new_balance,
            }
        )


# @api_view(["GET"])
# def credit_balance(request):
#     history = [
#         {
#             "date": now_iso(),
#             "amount": 100,
#             "type": "purchase",
#             "description": "Initial purchase",
#         },
#         {
#             "date": now_iso(),
#             "amount": -10,
#             "type": "spent",
#             "description": "Unlocked content",
#         },
#     ]
#     return Response({"balance": USER_BALANCES.get("default", 0), "history": history})


# # --- Subscription endpoints -------------------------------------------------


# @api_view(["GET"])
# def get_subscription(request):
#     sub = make_subscription(plan="premium")
#     return Response(sub)


# @api_view(["POST"])
# def subscribe_plan(request):
#     data = request.data or {}
#     plan = data.get("plan", "free")
#     sub = make_subscription(plan=plan)
#     return Response(sub, status=status.HTTP_201_CREATED)


# @api_view(["POST"])
# def upgrade_subscription(request):
#     data = request.data or {}
#     plan = data.get("plan", "premium")
#     sub = make_subscription(plan=plan)
#     return Response(sub)


# @api_view(["POST"])
# def downgrade_subscription(request):
#     data = request.data or {}
#     plan = data.get("plan", "free")
#     sub = make_subscription(plan=plan)
#     sub["status"] = "active" if plan != "free" else "downgraded"
#     return Response(sub)


# @api_view(["POST"])
# def cancel_subscription(request):
#     data = request.data or {}
#     immediate = data.get("immediate", False)
#     sub = make_subscription(plan="free")
#     sub["status"] = "cancelled" if immediate else "cancelled"
#     return Response(sub)


# @api_view(["POST"])
# def reactivate_subscription(request):
#     sub = make_subscription(plan="premium")
#     sub["status"] = "active"
#     return Response(sub)


# # --- Billing history & invoices --------------------------------------------


# @api_view(["GET"])
# def billing_history(request):
#     # Respect simple pagination params
#     limit = int(request.query_params.get("limit", 10))
#     items = [make_billing_history_item(i) for i in range(1, limit + 1)]
#     return Response(items)


# @api_view(["GET"])
# def get_invoice(request, invoice_id):
#     item = make_billing_history_item(1)
#     item["id"] = invoice_id
#     item["invoiceUrl"] = f"https://example.com/invoices/{invoice_id}.pdf"
#     return Response(item)


# @api_view(["GET"])
# def download_invoice(request, invoice_id):
#     # Return a download URL
#     return Response({"downloadUrl": f"https://example.com/invoices/{invoice_id}.pdf"})


# # --- Payment methods -------------------------------------------------------


# @api_view(["GET", "POST"])
# def payment_methods(request):
#     """
#     GET -> return list of payment methods
#     POST -> add a payment method (returns created method)
#     This consolidates get_payment_methods + add_payment_method into one endpoint.
#     """
#     global PAYMENT_METHODS

#     # POST: create a new payment method
#     if request.method == "POST":
#         payload = request.data or {}
#         m_id = str(uuid.uuid4())
#         method = {
#             "id": m_id,
#             "type": payload.get("type", "credit-card"),
#             "last4": payload.get("details", {}).get("last4", "4242"),
#             "isDefault": len(PAYMENT_METHODS) == 0,
#         }
#         PAYMENT_METHODS[m_id] = method
#         return Response(method, status=status.HTTP_201_CREATED)

#     # GET: return stored methods (or a default example when none exist)
#     methods = list(PAYMENT_METHODS.values()) or [
#         {"id": "pm_1", "type": "credit-card", "last4": "4242", "isDefault": True}
#     ]
#     return Response(methods)


# @api_view(["DELETE"])
# def remove_payment_method(request, method_id):
#     PAYMENT_METHODS.pop(method_id, None)
#     return Response({"success": True})


# @api_view(["POST"])
# def set_default_payment_method(request, method_id):
#     # mark the specified method as default
#     for mid, m in PAYMENT_METHODS.items():
#         m["isDefault"] = mid == method_id
#     return Response({"success": True})


# # --- Upcoming payments -----------------------------------------------------


# @api_view(["GET"])
# def get_upcoming_payments(request):
#     payments = [
#         {
#             "date": (
#                 datetime.datetime.utcnow() + datetime.timedelta(days=7)
#             ).isoformat()
#             + "Z",
#             "amount": 9.99,
#             "description": "Monthly subscription",
#             "type": "subscription",
#         }
#     ]
#     return Response(payments)


# # --- Refunds ---------------------------------------------------------------


# @api_view(["POST"])
# def request_refund(request):
#     data = request.data or {}
#     transaction_id = data.get("transactionId", str(uuid.uuid4()))  # noqa: F841
#     refund_id = str(uuid.uuid4())
#     REFUNDS[refund_id] = {
#         "id": refund_id,
#         "status": "pending",
#         "amount": 10.0,
#         "reason": data.get("reason", ""),
#     }
#     return Response({"success": True, "refundId": refund_id})


# @api_view(["GET"])
# def get_refund_status(request, refund_id):
#     r = REFUNDS.get(
#         refund_id, {"id": refund_id, "status": "pending", "amount": 0.0, "reason": ""}
#     )
#     return Response(r)


# # --- Promo and spending ---------------------------------------------------


# @api_view(["POST"])
# def apply_promo_code(request):
#     data = request.data or {}
#     code = data.get("code", "")
#     # simple mock rules
#     if code.lower() == "FREE100":
#         return Response(
#             {"valid": True, "discount": 100, "description": "Free 100 credits"}
#         )
#     return Response({"valid": False, "discount": 0, "description": "Invalid code"})


# @api_view(["GET"])
# def get_spending_summary(request):
#     period = request.query_params.get("period", "month")  # noqa: F841
#     return Response(
#         {
#             "total": round(random.uniform(10, 1000), 2),
#             "byCategory": {"subscriptions": 300, "credits": 150},
#             "trend": [
#                 {"date": now_iso(), "amount": round(random.uniform(0, 100), 2)}
#                 for _ in range(7)
#             ],
#         }
#     )


# # --- Unlock & pricing ------------------------------------------------------


# @api_view(["POST"])
# def unlock_content(request):
#     data = request.data or {}
#     content_id = data.get("contentId")  # noqa: F841
#     # Deduct 10 credits as mock
#     current = USER_BALANCES.get("default", 50)
#     used = min(current, 10)
#     USER_BALANCES["default"] = current - used
#     return Response(
#         {
#             "success": True,
#             "creditsUsed": used,
#             "remainingCredits": USER_BALANCES["default"],
#         }
#     )


class BillingSummaryView(APIView):
    """
    GET /api/v1/billing/summary?period=month|quarter|year

    Returns real-money spending totals aggregated from CREDIT_PURCHASE
    WalletTransactions. The Stripe webhook stores amount_received (minor
    units, e.g. cents) in metadata, so results are converted to dollars.
    """

    permission_classes = [IsAuthenticated]

    _PERIODS = {
        "month": relativedelta(months=1),
        "quarter": relativedelta(months=3),
        "year": relativedelta(years=1),
    }

    def get(self, request):
        period = request.query_params.get("period", "month")
        delta = self._PERIODS.get(period, self._PERIODS["month"])
        since = tz_now() - delta

        purchases = WalletTransaction.objects.filter(
            wallet__user=request.user,
            transaction_type=WalletTransaction.TransactionType.CREDIT_PURCHASE,
            created_at__gte=since,
        )

        total_cents = 0
        transactions = []
        for txn in purchases.order_by("-created_at"):
            cents = txn.metadata.get("amount_received") or 0
            try:
                cents = int(cents)
            except (TypeError, ValueError):
                cents = 0
            total_cents += cents
            transactions.append(
                {
                    "date": txn.created_at.isoformat(),
                    "amount": round(cents / 100, 2),
                    "currency": txn.metadata.get("currency", "usd"),
                    "credits": txn.amount,
                    "reference_id": txn.reference_id,
                }
            )

        return Response(
            {
                "period": period,
                "total": round(total_cents / 100, 2),
                "currency": "usd",
                "transactions": transactions,
            }
        )


# @api_view(["GET"])
# def get_content_pricing(request, content_id):
#     return Response(
#         {
#             "credits": 10,
#             "usdPrice": 1.99,
#             "discounts": [{"type": "promo", "amount": 0.5}],
#         }
#     )
