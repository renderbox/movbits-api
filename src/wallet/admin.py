from django.contrib import admin

from .models import Wallet, WalletTransaction


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "site", "credit_type", "balance", "updated_at")
    list_filter = ("site", "credit_type")
    search_fields = ("user__username", "user__email", "site__domain")
    autocomplete_fields = ("user", "site")
    list_select_related = ("user", "site")
    ordering = ("-updated_at",)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "wallet",
        "amount",
        "balance_after",
        "transaction_type",
        "reference_type",
        "reference_id",
        "stripe_payment_intent_id",
        "created_at",
    )
    list_filter = ("transaction_type", "reference_type")
    search_fields = (
        "wallet__user__email",
        "stripe_payment_intent_id",
        "reference_id",
    )
    list_select_related = ("wallet__user", "wallet__site")
    ordering = ("-created_at",)
    readonly_fields = (
        "wallet",
        "amount",
        "balance_after",
        "transaction_type",
        "reference_type",
        "reference_id",
        "stripe_payment_intent_id",
        "metadata",
        "created_at",
    )
