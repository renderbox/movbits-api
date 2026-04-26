import logging

# from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q  # , IntegerField,  When  # , Case
from django.utils import timezone, translation

# from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from vendor.config import DEFAULT_CURRENCY
from vendor.models import ProductModelBase

logger = logging.getLogger(__name__)


class CreditPackageManager(models.Manager):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(product_type=self.model.ProductType.CREDIT_PACKAGE)
        )


class Product(ProductModelBase):
    """Products that can be purchased by users with real money.
    This is starting with credit packages but can be nearly anything."""

    class ProductType(models.IntegerChoices):
        CREDIT_PACKAGE = 1, "Credit Package"
        SUBSCRIPTION = 2, "Subscription"
        # Add more product types as needed

    product_type = models.IntegerField(
        choices=ProductType.choices,
        default=ProductType.CREDIT_PACKAGE,
        help_text=_("Type of the product"),
    )

    credits = models.IntegerField(
        default=0,
        null=False,
        blank=False,
        help_text=_("Number of credits included in the product (optional)"),
    )
    bonus = models.IntegerField(
        default=0,
        null=False,
        blank=False,
        help_text=_("Number of bonus credits included in the product (optional)"),
    )

    objects = models.Manager()
    credit_packages = CreditPackageManager()

    # These will be move to django-vendor when we have a better idea of how to structure the offerings and prices.
    def get_current_offer(self):
        now = timezone.now()
        return (
            self.offers.filter(
                available=True,
                start_date__lte=now,
            )
            .filter(Q(end_date__isnull=True) | Q(end_date__gte=now))
            .first()
        )

    def get_current_price_object(self, currency=DEFAULT_CURRENCY):
        # """Returns the current price for the product, if an active one exists. # noqa: E501"""
        offer = self.get_current_offer()
        if offer is None:
            return None

        now = timezone.now()
        price = (
            offer.prices.filter(
                Q(start_date__lte=now) | Q(start_date=None),
                Q(end_date__gte=now) | Q(end_date=None),
                Q(currency=currency),
            )
            .order_by("-priority")
            .first()
        )  # first()/last() returns the model object or None

        return price

    def get_localized_description(self, lang=None):
        lang = lang or translation.get_language()
        return self.description.get(lang, {})

    def clean(self):
        super().clean()
        self.validate_description()

    def validate_description(self):
        """
        `description` must be:
        {
            "<lang>": {
                "body": str (optional),
                "bullets": [str, ...] (optional),
                "credits": int (optional),
                "heading": str (optional),
                "heading_color": str (optional)
            }
        }
        """
        if not isinstance(self.description, dict):
            raise ValidationError(
                "Descriptions must be a dictionary keyed by language codes."
            )

        for lang, data in self.description.items():
            if not isinstance(data, dict):
                raise ValidationError(
                    f"Entry for language '{lang}' must be a dictionary."
                )

            # Expected types when present
            optional_fields = {
                "body": str,
                "bullets": list,
                "credits": int,
                "heading": str,
                "heading_color": str,
            }

            for field, expected_type in optional_fields.items():
                if field not in data:
                    continue  # optional → skip

                value = data[field]

                if not isinstance(value, expected_type):
                    raise ValidationError(
                        f"Field '{field}' in '{lang}' must be of type {expected_type.__name__} when provided."
                    )

                # Special rule: bullets must be a list of strings
                if field == "bullets" and not all(isinstance(b, str) for b in value):
                    raise ValidationError(f"All 'bullets' in '{lang}' must be strings.")
