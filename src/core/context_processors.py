def wallet_balance(request):
    if request.user.is_authenticated:
        from wallet.models import Wallet

        try:
            wallet = Wallet.objects.get(user=request.user)
            return {"wallet_balance": wallet.balance}
        except Wallet.DoesNotExist:
            return {"wallet_balance": 0}
    return {"wallet_balance": 0}
