from django.urls import path

from . import views

urlpatterns = [
    path("stats", views.admin_stats, name="admin_stats"),
    # Users
    path("users", views.admin_users_list, name="admin_users_list"),
    path(
        "users/<str:user_id>/status",
        views.admin_user_update_status,
        name="admin_user_update_status",
    ),
    path(
        "users/<str:user_id>/role",
        views.admin_user_update_role,
        name="admin_user_update_role",
    ),
    path("users/<str:user_id>/ban", views.admin_user_ban, name="admin_user_ban"),
    path("users/<str:user_id>/unban", views.admin_user_unban, name="admin_user_unban"),
    path("users/<str:user_id>", views.admin_user_detail, name="admin_user_detail"),
    # Content review
    path("content/pending", views.admin_pending_content, name="admin_pending_content"),
    path(
        "content/reviews/<str:review_id>",
        views.admin_content_review_detail,
        name="admin_content_review_detail",
    ),
    path(
        "content/<str:content_id>/approve",
        views.admin_content_approve,
        name="admin_content_approve",
    ),
    path(
        "content/<str:content_id>/reject",
        views.admin_content_reject,
        name="admin_content_reject",
    ),
    path(
        "content/<str:content_id>/flag",
        views.admin_content_flag,
        name="admin_content_flag",
    ),
    path("content/stats", views.admin_content_stats, name="admin_content_stats"),
    # Transactions
    path("transactions", views.admin_transactions_list, name="admin_transactions_list"),
    path(
        "transactions/<str:transaction_id>",
        views.admin_transaction_detail,
        name="admin_transaction_detail",
    ),
    path(
        "transactions/<str:transaction_id>/refund",
        views.admin_transaction_refund,
        name="admin_transaction_refund",
    ),
    # System
    path("system/health", views.admin_system_health, name="admin_system_health"),
    # Revenue & growth
    path("revenue", views.admin_revenue_stats, name="admin_revenue_stats"),
    path("users/growth", views.admin_user_growth_stats, name="admin_user_growth_stats"),
    # Platform tools
    path(
        "announcements", views.admin_send_announcement, name="admin_send_announcement"
    ),
    path("settings", views.admin_platform_settings, name="admin_platform_settings"),
    path(
        "reports/<str:report_type>/export",
        views.admin_export_report,
        name="admin_export_report",
    ),
]
