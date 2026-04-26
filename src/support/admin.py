from django.contrib import admin

from .models import (
    HelpArticle,
    HelpArticleTranslation,
    HelpCategory,
    HelpCategoryTranslation,
    HelpFAQ,
    HelpFAQTranslation,
    SupportTicket,
    TicketAttachment,
    TicketMessage,
)

# ── Ticket Admin ──────────────────────────────────────────────────────────────


class TicketMessageInline(admin.StackedInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ["timestamp"]
    show_change_link = True


class TicketAttachmentInline(admin.TabularInline):
    model = TicketAttachment
    extra = 0
    readonly_fields = ["uploaded_at"]


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "subject",
        "user",
        "category",
        "priority",
        "status",
        "created_at",
    ]
    list_filter = ["status", "priority", "category"]
    search_fields = ["subject", "description", "user__email", "user__username"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [TicketMessageInline]


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ["id", "ticket", "sender", "sender_role", "timestamp"]
    readonly_fields = ["timestamp"]
    inlines = [TicketAttachmentInline]


# ── Help Center Admin ─────────────────────────────────────────────────────────


class HelpCategoryTranslationInline(admin.TabularInline):
    model = HelpCategoryTranslation
    extra = 1


@admin.register(HelpCategory)
class HelpCategoryAdmin(admin.ModelAdmin):
    list_display = ["slug", "icon", "color", "order", "is_active"]
    list_editable = ["order", "is_active"]
    inlines = [HelpCategoryTranslationInline]


class HelpArticleTranslationInline(admin.TabularInline):
    model = HelpArticleTranslation
    extra = 1


@admin.register(HelpArticle)
class HelpArticleAdmin(admin.ModelAdmin):
    list_display = [
        "slug",
        "category",
        "read_time_minutes",
        "is_popular",
        "is_active",
        "updated_at",
    ]
    list_filter = ["category", "is_popular", "is_active"]
    list_editable = ["is_popular", "is_active"]
    inlines = [HelpArticleTranslationInline]


class HelpFAQTranslationInline(admin.TabularInline):
    model = HelpFAQTranslation
    extra = 1


@admin.register(HelpFAQ)
class HelpFAQAdmin(admin.ModelAdmin):
    list_display = ["id", "category", "order", "is_active"]
    list_filter = ["category", "is_active"]
    list_editable = ["order", "is_active"]
    inlines = [HelpFAQTranslationInline]
