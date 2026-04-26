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


class WalletSerializer(serializers.ModelSerializer):
    credit_type_label = serializers.CharField(
        source="get_credit_type_display", read_only=True
    )
    transactions = WalletTransactionSerializer(many=True, read_only=True)

    class Meta:
        model = Wallet
        fields = [
            "id",
            "balance",
            "credit_type",
            "credit_type_label",
            "transactions",
            "updated_at",
        ]
