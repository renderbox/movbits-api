import math

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import get_language
from rest_framework import serializers
from vendor.config import DEFAULT_CURRENCY
from vendor.models import Invoice, Offer, OrderItem
from vendor.utils import get_site_from_request

# from locale import currency


# class CreditPackageDescriptionSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = CreditPackageDescription
#         fields = ("language", "header", "bullet_points")


# class CreditPackageSerializer(serializers.ModelSerializer):
#     pass


#     description = serializers.SerializerMethodField()
#     currency = serializers.SerializerMethodField()

#     class Meta:
#         model = Product
#         fields = [
#             "id",
#             # "credits",
#             # "price",
#             "currency",  # Human-readable currency label (e.g., "USD")
#             "description",
#         ]

#     def get_description(self, obj):
#         # language = get_language()  # Get current language from request context
#         # try:
#         #     desc = obj.descriptions.get(language=language)
#         # except CreditPackageDescription.DoesNotExist:
#         #     # Optionally fall back to default language or return None
#         #     desc = obj.descriptions.filter(language="en").first()
#         # return CreditPackageDescriptionSerializer(desc).data if desc else None
#         return "Description feature not implemented."

#     def get_currency(self, obj):
#         # Map stored integer choice to its display label (e.g., "USD")
#         return obj.get_real_currency_display()


class CreatePaymentIntentSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)
    currency = serializers.CharField(max_length=10)

    def validate_currency(self, value):
        return value.lower().strip()

    @staticmethod
    def _refresh_cart(cart):
        try:
            cart.update_totals()
        except AttributeError:
            try:
                cart.save()
            except Exception:
                pass

    def validate(self, attrs):
        request = self.context.get("request")
        if request is None:
            raise serializers.ValidationError(
                {"detail": "Request context is required."}
            )

        site = get_site_from_request(request)
        profile, _ = request.user.customer_profile.get_or_create(site=site)
        cart = profile.get_cart()

        self._refresh_cart(cart)

        items = cart.order_items.all()

        if not items:
            raise serializers.ValidationError({"detail": "Cart is empty."})

        expected_total = cart.total
        expected_currency = cart.currency

        if expected_total is None or expected_currency is None:
            raise serializers.ValidationError({"detail": "Cart total is unavailable."})

        try:
            expected_total = int(expected_total)
        except (TypeError, ValueError):
            raise serializers.ValidationError({"detail": "Cart total is unavailable."})

        if expected_total <= 0:
            raise serializers.ValidationError({"detail": "Cart total is invalid."})

        expected_currency = str(expected_currency).lower()
        posted_amount = attrs["amount"]
        posted_currency = attrs["currency"]

        if posted_amount != expected_total or posted_currency != expected_currency:
            raise serializers.ValidationError(
                {"detail": "Posted total does not match the cart."}
            )

        attrs["cart"] = cart
        attrs["profile"] = profile
        attrs["expected_total"] = expected_total
        attrs["expected_currency"] = expected_currency
        return attrs


class CreditPackageSerializer(serializers.ModelSerializer):

    name = serializers.SerializerMethodField()
    slug = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    msrp = serializers.SerializerMethodField()
    discount = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()

    class Meta:
        model = Offer
        fields = [
            "uuid",
            "name",
            "description",
            "price",
            "msrp",
            "discount",
            "currency",
            "slug",
        ]

    def _get_price_object(self, obj):
        now = self.context.get("now")
        if now is None:
            now = timezone.now()
        prefetched = getattr(obj, "_prefetched_objects_cache", {}).get("prices")
        if prefetched is not None:
            active = [
                price
                for price in prefetched
                if (
                    (price.start_date is None or price.start_date <= now)
                    and (price.end_date is None or price.end_date >= now)
                    and price.currency == DEFAULT_CURRENCY
                )
            ]
            if active:
                return max(active, key=lambda price: price.priority or 0)
        return (
            obj.prices.filter(
                Q(start_date__lte=now) | Q(start_date=None),
                Q(end_date__gte=now) | Q(end_date=None),
                Q(currency=DEFAULT_CURRENCY),
            )
            .order_by("-priority")
            .first()
        )

    def _get_product(self, obj):
        prefetched = getattr(obj, "_prefetched_objects_cache", {}).get("products")
        if prefetched is not None:
            return prefetched[0] if prefetched else None
        if hasattr(obj, "products"):
            return obj.products.first()
        return None

    def get_name(self, obj):
        product = self._get_product(obj)
        return getattr(product, "name", None)

    def get_slug(self, obj):
        product = self._get_product(obj)
        return getattr(product, "slug", None)

    def get_price(self, obj):
        """Temporary until Django-Vendor is updated to support cents (integers) instead of floating point values"""
        price = self._get_price_object(obj)
        return int(math.ceil(price.cost)) if price else None

    def get_description(self, obj):
        product = self._get_product(obj)
        description = getattr(product, "description", None)
        if not isinstance(description, dict):
            return None

        language = get_language() or settings.LANGUAGE_CODE
        if language in description:
            return description[language]

        language_base = language.split("-", 1)[0]
        if language_base in description:
            return description[language_base]

        default_language = settings.LANGUAGE_CODE
        if default_language in description:
            return description[default_language]

        default_base = default_language.split("-", 1)[0]
        return description.get(default_base)

    def get_msrp(self, obj):
        product = self._get_product(obj)
        meta = getattr(product, "meta", None)
        if not isinstance(meta, dict):
            return None
        msrp = meta.get("msrp")
        if not isinstance(msrp, dict):
            return None
        default_currency = msrp.get("default")
        if not default_currency:
            return None
        return msrp.get(default_currency)

    def get_discount(self, obj):
        product = self._get_product(obj)
        meta = getattr(product, "meta", None)
        if not isinstance(meta, dict):
            return None
        msrp = meta.get("msrp")
        if not isinstance(msrp, dict):
            return None
        default_currency = msrp.get("default")
        if not default_currency:
            return None
        msrp_price = msrp.get(default_currency)
        current_price = self.get_price(obj)
        if msrp_price and current_price:
            discount_amount = msrp_price - current_price
            discount_percent = discount_amount / msrp_price
            return round(discount_percent, 2)
        return None

    def get_currency(self, obj):
        price = self._get_price_object(obj)
        if not price:
            return None
        currency = price.currency
        return currency if currency else None
        # if currency is None:
        #     return None
        # return obj.get_real_currency_display()


class OfferSerializer(serializers.ModelSerializer):
    unit_price = serializers.SerializerMethodField()
    msrp = serializers.SerializerMethodField()

    class Meta:
        model = Offer
        fields = [
            "id",
            "name",
            "description",
            "unit_price",
            "msrp",
            # Add any other relevant fields from the Product model
        ]

    def get_unit_price(self, obj):
        return obj.current_price()

    def get_msrp(self, obj):
        return obj.get_msrp()


class OrderItemSerializer(serializers.ModelSerializer):
    """Individual items in the invoice, flattened"""

    total = serializers.SerializerMethodField()
    offer_id = serializers.UUIDField(source="offer.uuid", read_only=True)
    name = serializers.UUIDField(source="offer.name", read_only=True)
    description = serializers.UUIDField(source="offer.description", read_only=True)
    unit_price = serializers.SerializerMethodField()
    msrp = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "offer_id",
            "quantity",
            "total",
            "name",
            "description",
            "unit_price",
            "msrp",
        )

    # TODO: add an optional "credits" field that will calculate the total credits for this line item based on the offer's products and their associated credit values (if any). This will require a bit of custom logic to look up the products associated with the offer, determine their credit values, and multiply by the quantity of the line item.  # noqa: E501

    def get_total(self, obj):
        quantity = obj.quantity
        unit_price = obj.offer.current_price() if obj.offer else 0
        return quantity * unit_price if unit_price is not None else None

    def get_unit_price(self, obj):
        return obj.offer.current_price() if obj.offer else None

    def get_msrp(self, obj):
        return obj.offer.get_msrp() if obj.offer else None


class VendorInvoiceSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True)
    subtotal = serializers.SerializerMethodField()
    tax = serializers.SerializerMethodField()
    discount = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = "__all__"

    def _serialize_line_item(self, item):
        product = getattr(item, "product", None)
        return {
            "id": getattr(item, "id", None),
            "uuid": getattr(item, "uuid", None),
            "product_id": getattr(item, "product_id", None)
            or getattr(product, "id", None),
            "name": getattr(item, "name", None) or getattr(product, "name", None),
            "quantity": getattr(item, "quantity", None),
            "unit_price": getattr(item, "price", None),
            "total": getattr(item, "total", None),
            "currency": getattr(item.invoice, "currency", None),
        }

    def get_line_items(self, obj):
        return [self._serialize_line_item(item) for item in obj.order_items.all()]

    def get_subtotal(self, obj):
        return obj.subtotal

    def get_tax(self, obj):
        return obj.tax

    def get_discount(self, obj):
        return obj.global_discount

    def get_total(self, obj):
        return obj.total

    def get_currency(self, obj):
        return obj.currency


class CartSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True)
    total_credits = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = (
            "uuid",
            "order_items",
            "subtotal",
            "tax",
            "total",
            "currency",
            "total_credits",
        )

    def get_total_credits(self, item):
        # TODO: implement logic to calculate total credits for the cart based on the products in the line items, quantities and their associated credit values (if any). This will require looking up each product associated with the line items, determining its credit value, and multiplying by the quantity of that line item, then summing across all line items to get a total credit value for the cart.  # noqa: E501
        return 100


class CreditCartSerializer(serializers.ModelSerializer):
    line_items = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    total_credits = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = "__all__"

    def _serialize_line_item(self, item):
        product = getattr(item, "product", None)
        return {
            "id": getattr(item, "id", None),
            "uuid": getattr(item, "uuid", None),
            "product_id": getattr(item, "product_id", None)
            or getattr(product, "id", None),
            "name": getattr(item, "name", None) or getattr(product, "name", None),
            "quantity": getattr(item, "quantity", None),
            "unit_price": getattr(item, "unit_price", None),
            "total": getattr(item, "total", None),
            "currency": getattr(item, "currency", None),
        }

    def get_line_items(self, obj):
        return [self._serialize_line_item(item) for item in obj.order_items.all()]

    def _resolve_credits(self, product):
        if not product:
            return 0

        credits = getattr(product, "credits", None)
        try:
            return int(credits) if credits is not None else 0
        except (TypeError, ValueError):
            return 0

    def get_total_credits(self, obj):
        total = 0

        for item in obj.order_items.all():
            # TODO: If the order item has a "credits" add it to the total multiplied by the "quantity", otherwise ignore.
            #       Keep it simple.

            quantity = getattr(item, "quantity", None) or 1
            product = getattr(item, "product", None)
            if product:
                total += self._resolve_credits(product) * quantity
                continue

            offer = getattr(item, "offer", None)
            if offer and hasattr(offer, "products"):
                for offer_product in offer.products.all():
                    total += self._resolve_credits(offer_product) * quantity

        return total

    def get_total(self, obj):
        return obj.total
