from django.contrib import admin

from .models import Campaign, SiteInvitation

# django-invitations registers the swapped model automatically via its own
# InvitationAdmin — unregister it so we can register our custom admin below.
try:
    admin.site.unregister(SiteInvitation)
except admin.sites.NotRegistered:
    pass


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ["title", "created_by", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(SiteInvitation)
class SiteInvitationAdmin(admin.ModelAdmin):
    list_display = ["email", "name", "campaign", "sent", "accepted", "key_expired"]
    readonly_fields = ["key", "sent", "accepted", "created"]
    list_filter = ["campaign"]
    search_fields = ["email", "name"]
