from django.contrib import admin

from .models import ReferralLink


@admin.register(ReferralLink)
class ReferralLinkAdmin(admin.ModelAdmin):
    # list_display = ("name", "team", "episode", "slug", "deleted")
    # list_filter = ("team", "deleted")
    # search_fields = ("name", "slug", "team__name", "episode__title")
    prepopulated_fields = {"slug": ("name",)}
