from django.urls import path

from . import views

urlpatterns = [
    # Credit packages & purchases
    path(
        "credits/packages",
        views.CreditPackageListView.as_view(),
        name="billing-credit-packages",
    ),
    path(
        "cart",
        views.CartView.as_view(),
        name="billing-edit-cart",
    ),
    path(
        "cart/",
        views.CartView.as_view(),
        name="billing-edit-cart-slash",
    ),
    path(
        "payment-intent",
        views.CreatePaymentIntentView.as_view(),
        name="billing-create-payment-intent",
    ),
    path(
        "stripe-webhook",
        views.StripeWebhookView.as_view(),
        name="billing-stripe-webhook",
    ),
    path(
        "credits/purchase",
        views.PurchaseCreditsSuccessView.as_view(),
        name="billing_purchase_credits",
    ),
    path(
        "one-click",
        views.OneClickPurchaseView.as_view(),
        name="billing_one_click_purchase",
    ),
    path(
        "customer-portal",
        views.CustomerPortalView.as_view(),
        name="billing_customer_portal",
    ),
    path(
        "summary",
        views.BillingSummaryView.as_view(),
        name="billing-summary",
    ),
    # path("credits/balance", views.credit_balance, name="billing_credit_balance"),
    # # Subscriptions
    # path("subscription", views.get_subscription, name="billing_get_subscription"),
    # path("subscription/subscribe", views.subscribe_plan, name="billing_subscribe"),
    # path(
    #     "subscription/upgrade",
    #     views.upgrade_subscription,
    #     name="billing_upgrade",
    # ),
    # path(
    #     "subscription/downgrade",
    #     views.downgrade_subscription,
    #     name="billing_downgrade",
    # ),
    # path(
    #     "subscription/cancel",
    #     views.cancel_subscription,
    #     name="billing_cancel_subscription",
    # ),
    # path(
    #     "subscription/reactivate",
    #     views.reactivate_subscription,
    #     name="billing_reactivate",
    # ),
    # # Billing history & invoices
    # path("history", views.billing_history, name="billing_history"),
    # path(
    #     "invoices/<str:invoice_id>",
    #     views.get_invoice,
    #     name="billing_get_invoice",
    # ),
    # path(
    #     "invoices/<str:invoice_id>/download",
    #     views.download_invoice,
    #     name="billing_download_invoice",
    # ),
    # # Payment methods
    # path("payment-methods", views.payment_methods, name="billing_payment_methods"),
    # path(
    #     "payment-methods/<str:method_id>",
    #     views.remove_payment_method,
    #     name="billing_remove_payment_method",
    # ),
    # path(
    #     "payment-methods/<str:method_id>/default",
    #     views.set_default_payment_method,
    #     name="billing_set_default_payment_method",
    # ),
    # # Upcoming payments
    # path("upcoming", views.get_upcoming_payments, name="billing_upcoming"),
    # # Refunds
    # path("refunds/request", views.request_refund, name="billing_request_refund"),
    # path(
    #     "refunds/<str:refund_id>",
    #     views.get_refund_status,
    #     name="billing_refund_status",
    # ),
]
