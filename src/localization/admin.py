from django.contrib import admin

from .models import Language, Translation


class TranslationInline(admin.TabularInline):
    model = Translation
    extra = 1
    fields = ("key", "value")
    ordering = ("key",)


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "code",
        "flag",
        "is_rtl",
        "is_active",
        "translation_count",
    )
    list_filter = ("is_active", "is_rtl")
    search_fields = ("code", "display_name", "name")
    inlines = (TranslationInline,)

    def translation_count(self, obj):
        return obj.translations.count()

    translation_count.short_description = "Keys"


@admin.register(Translation)
class TranslationAdmin(admin.ModelAdmin):
    list_display = ("key", "language", "value")
    list_filter = ("language",)
    search_fields = ("key", "value")
    ordering = ("language__code", "key")
