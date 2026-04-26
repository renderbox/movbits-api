from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.context_processors import wallet_balance


class ContextProcessorTests(TestCase):
    @patch("wallet.models.Wallet.objects.get")
    def test_wallet_balance_context_processor(self, mock_get_wallet):
        """Test that the wallet_balance context processor adds the correct data."""
        mock_wallet = MagicMock()
        mock_wallet.balance = 100
        mock_get_wallet.return_value = mock_wallet

        mock_request = MagicMock()
        mock_request.user.is_authenticated = True

        context = wallet_balance(mock_request)
        self.assertEqual(context["wallet_balance"], 100)
