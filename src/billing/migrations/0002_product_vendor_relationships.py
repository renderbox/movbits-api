from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Adds the vendor M2M relationships to billing.Product.
    Must run after vendor's full chain to avoid the swappable-dependency cycle:
      vendor.0001 → billing.0001 (swappable product model)
      billing.0002 → vendor.0049 (M2M targets exist)
    """

    dependencies = [
        ("billing", "0001_initial"),
        ("vendor", "0049_alter_invoice_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="classification",
            field=models.ManyToManyField(blank=True, to="vendor.taxclassifier"),
        ),
        migrations.AddField(
            model_name="product",
            name="offers",
            field=models.ManyToManyField(
                blank=True, related_name="products", to="vendor.offer"
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="receipts",
            field=models.ManyToManyField(
                blank=True, related_name="products", to="vendor.receipt"
            ),
        ),
    ]
