from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import FeatureFlag, Profile, StoryUser


@admin.register(StoryUser)
class StoryUserAdmin(BaseUserAdmin):
    # 1) Change form (editing an existing user)
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            _("Personal info"),
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "date_of_birth",  # ← new
                )
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    # 2) Add form (creating a new user)
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "date_of_birth",  # ← include here too
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    # 3) Columns on the user list page
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "age",  # ← show computed age
        "is_staff",
    )

    search_fields = (
        "username",
        "first_name",
        "last_name",
        "email",
    )
    ordering = ("username",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "site", "role")
    search_fields = ("user__email", "site__domain", "role")


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "value", "value_type", "is_active")
    search_fields = ("name", "key", "value")
    list_filter = ("value_type", "is_active")
    filter_horizontal = ("sites", "permissions")
