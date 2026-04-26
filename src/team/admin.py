from django.contrib import admin

from .models import Team, TeamInvite, TeamMembership


class TeamMembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 1
    list_display = ("user", "role")
    list_filter = ("role",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sites_list")
    search_fields = ("name", "sites__domain")
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ("sites",)
    inlines = [TeamMembershipInline]
    readonly_fields = ("uuid",)

    def sites_list(self, obj):
        return ", ".join([site.domain for site in obj.sites.all()])

    sites_list.short_description = "Sites"


@admin.register(TeamInvite)
class TeamInviteAdmin(admin.ModelAdmin):
    list_display = ("email", "team", "token", "created_at", "accepted_at", "expires_at")
    search_fields = ("email", "team__name", "token")
    list_filter = ("team", "created_at", "accepted_at", "expires_at")
