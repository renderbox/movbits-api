from django.contrib import admin

from .models import InterestedUser, Survey, SurveyResult


@admin.register(InterestedUser)
class InterestedUserAdmin(admin.ModelAdmin):
    list_display = ("email", "site", "added_at", "user")
    search_fields = ("email",)
    list_filter = ("site", "added_at")


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ("title", "survey_type", "created_at", "is_active")
    search_fields = ("title",)
    list_filter = ("survey_type", "is_active", "created_at")


@admin.register(SurveyResult)
class SurveyResultsAdmin(admin.ModelAdmin):
    list_display = ("email", "user", "submitted_at")
    search_fields = ("email",)
    list_filter = ("submitted_at",)
