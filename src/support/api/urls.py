from django.urls import path

from . import views

urlpatterns = [
    # Static ticket routes — must come before <ticket_id> to avoid capture
    path("tickets", views.tickets_list, name="tickets_list"),
    path("tickets/stats", views.tickets_stats, name="tickets_stats"),
    path("tickets/search", views.tickets_search, name="tickets_search"),
    path(
        "tickets/unread/count", views.tickets_unread_count, name="tickets_unread_count"
    ),
    # Ticket detail (parameterized)
    path("tickets/<str:ticket_id>", views.ticket_detail, name="ticket_detail"),
    path(
        "tickets/<str:ticket_id>/messages",
        views.ticket_messages,
        name="ticket_add_message",
    ),
    path(
        "tickets/<str:ticket_id>/status",
        views.ticket_update_status,
        name="ticket_update_status",
    ),
    path(
        "tickets/<str:ticket_id>/priority",
        views.ticket_update_priority,
        name="ticket_update_priority",
    ),
    path("tickets/<str:ticket_id>/assign", views.ticket_assign, name="ticket_assign"),
    path("tickets/<str:ticket_id>/close", views.ticket_close, name="ticket_close"),
    path("tickets/<str:ticket_id>/reopen", views.ticket_reopen, name="ticket_reopen"),
    path(
        "tickets/<str:ticket_id>/attachments",
        views.ticket_upload_attachment,
        name="ticket_upload_attachment",
    ),
    path(
        "tickets/<str:ticket_id>/read", views.ticket_mark_read, name="ticket_mark_read"
    ),
    # Admin
    path("admin/tickets", views.admin_tickets_list, name="admin_tickets_list"),
    # Help Center (public)
    path("help/categories", views.HelpCategoriesView.as_view(), name="help_categories"),
    path("help/articles", views.HelpArticlesView.as_view(), name="help_articles"),
    path(
        "help/articles/<int:article_id>",
        views.HelpArticleDetailView.as_view(),
        name="help_article_detail",
    ),
    path("help/faqs", views.HelpFAQsView.as_view(), name="help_faqs"),
]
