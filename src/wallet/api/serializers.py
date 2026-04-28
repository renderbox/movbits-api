from datetime import date

from django.db.models import Sum
from rest_framework import serializers

from ..models import Wallet, WalletTransaction


class WalletTransactionSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source="get_transaction_type_display", read_only=True)

    class Meta:
        model = WalletTransaction
        fields = [
            "id",
            "amount",
            "balance_after",
            "type",
            "reference_type",
            "reference_id",
            "metadata",
            "created_at",
        ]


def _spending_summary(wallet):
    debits = wallet.transactions.filter(amount__lt=0)

    today = date.today()
    first_of_month = today.replace(day=1)
    if today.month == 1:
        first_of_last_month = today.replace(year=today.year - 1, month=12, day=1)
        first_of_next_month = today.replace(month=2, day=1)
    else:
        first_of_last_month = today.replace(month=today.month - 1, day=1)
        first_of_next_month = (
            today.replace(month=today.month + 1, day=1)
            if today.month < 12
            else today.replace(year=today.year + 1, month=1, day=1)
        )

    def _abs_sum(qs):
        result = qs.aggregate(total=Sum("amount"))["total"]
        return abs(result) if result else 0

    return {
        "all_time": _abs_sum(debits),
        "this_month": _abs_sum(
            debits.filter(
                created_at__date__gte=first_of_month,
                created_at__date__lt=first_of_next_month,
            )
        ),
        "last_month": _abs_sum(
            debits.filter(
                created_at__date__gte=first_of_last_month,
                created_at__date__lt=first_of_month,
            )
        ),
    }


class WalletSerializer(serializers.ModelSerializer):
    credit_type_label = serializers.CharField(
        source="get_credit_type_display", read_only=True
    )
    transactions = WalletTransactionSerializer(many=True, read_only=True)
    spending_summary = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = [
            "id",
            "balance",
            "credit_type",
            "credit_type_label",
            "transactions",
            "spending_summary",
            "updated_at",
        ]

    def get_spending_summary(self, obj):
        return _spending_summary(obj)
