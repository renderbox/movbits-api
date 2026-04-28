import uuid

import django.contrib.sites.managers
import django.db.models.deletion
import django.db.models.manager
import vendor.fields
import vendor.models.base
import vendor.models.validator
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.CreateModel(
            name="Product",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="date created"
                    ),
                ),
                (
                    "updated",
                    models.DateTimeField(auto_now=True, verbose_name="last updated"),
                ),
                (
                    "sku",
                    models.CharField(
                        blank=True,
                        help_text="User Defineable SKU field",
                        max_length=40,
                        null=True,
                        unique=True,
                        verbose_name="SKU",
                    ),
                ),
                (
                    "uuid",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ("name", models.CharField(max_length=80, verbose_name="Name")),
                (
                    "slug",
                    vendor.fields.AutoSlugField(
                        editable=False, populate_from="name", unique_with=("site__id",)
                    ),
                ),
                (
                    "available",
                    models.BooleanField(
                        default=False,
                        help_text="Is this currently available?",
                        verbose_name="Available",
                    ),
                ),
                (
                    "description",
                    models.JSONField(
                        blank=True,
                        default=vendor.models.base.product_description_default,
                        help_text="Eg: {'call out': 'The ultimate product'}",
                        null=True,
                        verbose_name="Description",
                    ),
                ),
                (
                    "meta",
                    models.JSONField(
                        blank=True,
                        default=vendor.models.base.product_meta_default,
                        help_text="Eg: { 'msrp':{'usd':10.99} }\n(iso4217 Country Code):(MSRP Price)",
                        null=True,
                        validators=[vendor.models.validator.validate_msrp],
                        verbose_name="Meta",
                    ),
                ),
                (
                    "product_type",
                    models.IntegerField(
                        choices=[(1, "Credit Package"), (2, "Subscription")],
                        default=1,
                        help_text="Type of the product",
                    ),
                ),
                (
                    "credits",
                    models.IntegerField(
                        default=0,
                        help_text="Number of credits included in the product (optional)",
                    ),
                ),
                (
                    "bonus",
                    models.IntegerField(
                        default=0,
                        help_text="Number of bonus credits included in the product (optional)",
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        default=1,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="products",
                        to="sites.site",
                        verbose_name="Site",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("on_site", django.contrib.sites.managers.CurrentSiteManager()),
            ],
        ),
    ]
