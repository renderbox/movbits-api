from django.conf import settings
from django.contrib.sites.models import Site
from django.db import models


class CreditTypes(models.IntegerChoices):
    CREDIT = 1, "MovBits Credits"
    BONUS = 2, "MovBits Bonus Credits"


class Wallet(models.Model):
    """
    This is a Wallet for managing virtual currency (credits) for users.
    Each user can have multiple wallets, but only one per site and credit type.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallets"
    )
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="wallets")
    credit_type = models.IntegerField(
        choices=CreditTypes.choices, default=CreditTypes.CREDIT
    )
    balance = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "user", "credit_type"],
                name="unique_wallet_per_site_user_type",
            )
        ]

    def __str__(self):
        credit_label = CreditTypes(self.credit_type).label
        return (
            f"{self.user.get_username()} - {self.site.domain} - {credit_label}: "
            f"{self.balance}"
        )


class WalletTransaction(models.Model):
    """
    Append-only ledger of every credit movement on a Wallet.

    Each row records a single debit or credit with a balance snapshot,
    so the full history can be reconstructed and audited without relying
    solely on the current Wallet.balance value.

    amount > 0  →  credits added   (e.g. Stripe purchase, bonus grant)
    amount < 0  →  credits deducted (e.g. video unlock)
    """

    class TransactionType(models.IntegerChoices):
        CREDIT_PURCHASE = 1, "Credit Purchase"
        VIDEO_UNLOCK = 2, "Video Unlock"
        BONUS_GRANT = 3, "Bonus Grant"
        REFUND = 4, "Refund"
        CREDIT_EXPIRY = 5, "Credit Expiry"
        ADMIN_ADJUSTMENT = 6, "Admin Adjustment"

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    amount = models.IntegerField(
        help_text="Credits added (positive) or deducted (negative).",
    )
    balance_after = models.IntegerField(
        help_text="Wallet balance immediately after this transaction.",
    )
    transaction_type = models.IntegerField(choices=TransactionType.choices)

    # Polymorphic reference to the source object (invoice, receipt, etc.)
    reference_type = models.CharField(
        max_length=50,
        blank=True,
        help_text='Source object type, e.g. "stripe_invoice", "video_receipt", "admin".',
    )
    reference_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="UUID or PK of the source object.",
    )

    # Stripe — indexed for direct lookups from webhook payloads
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Stripe PaymentIntent ID, present on CREDIT_PURCHASE transactions.",
    )

    # Flexible extra context (video slug, package name, show, etc.)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        sign = "+" if self.amount >= 0 else ""
        return (
            f"{self.wallet} | {sign}{self.amount} credits "
            f"→ balance {self.balance_after} [{self.get_transaction_type_display()}]"
        )
