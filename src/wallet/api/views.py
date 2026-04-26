from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import CreditTypes, Wallet
from .serializers import WalletSerializer


class WalletDetailView(APIView):
    """
    GET /api/v1/wallet/
    Returns the authenticated user's credit wallet and recent transaction history.
    Creates the wallet on first access if it doesn't exist yet.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        wallet, _ = Wallet.objects.get_or_create(
            user=request.user,
            site=request.site,
            credit_type=CreditTypes.CREDIT,
        )
        serializer = WalletSerializer(wallet)
        return Response(serializer.data)
