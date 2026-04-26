# from django.contrib import admin

# from .models import (
#     Chapter,
#     ChapterView,
#     Episode,
#     LibraryEntry,
#     Series,
#     SeriesMarketing,
#     SeriesStats,
# )

# class SeriesStatsInline(admin.StackedInline):
#     model = SeriesStats
#     can_delete = False
#     verbose_name_plural = "Series Stats"
#     fk_name = "series"
#     extra = 0
#     fields = ("site", "views", "likes", "dislikes")
#     autocomplete_fields = ("site",)


# class SeriesMarketingInline(admin.TabularInline):
#     model = SeriesMarketing
#     extra = 0
#     fields = ("placement", "site", "order")
#     autocomplete_fields = ("site",)
#     show_change_link = True


# @admin.register(Series)
# class SeriesAdmin(admin.ModelAdmin):
#     list_display = ("title", "team", "min_age", "created_at", "updated_at")
#     search_fields = ("title", "description")
#     prepopulated_fields = {"slug": ("title",)}
#     list_filter = ("team", "min_age", "created_at")
#     readonly_fields = ("created_at", "updated_at")
#     filter_horizontal = ("sites",)
#     fields = (
#         "title",
#         "slug",
#         "description",
#         "team",
#         "min_age",
#         "poster",
#         "sites",
#         "created_at",
#         "updated_at",
#     )
#     inlines = [SeriesStatsInline, SeriesMarketingInline]


# class ChapterInline(admin.TabularInline):
#     model = Chapter
#     extra = 1
#     fields = ("chapter_number", "title", "video_url", "cdn")


# @admin.register(Episode)
# class EpisodeAdmin(admin.ModelAdmin):
#     list_display = ("title", "series", "price", "created_at", "uuid")
#     search_fields = ("title", "description")
#     prepopulated_fields = {"slug": ("title",)}
#     list_filter = ("series", "price")
#     readonly_fields = ("uuid",)
#     inlines = [ChapterInline]


# @admin.register(Chapter)
# class ChapterAdmin(admin.ModelAdmin):
#     list_display = ("title", "episode", "chapter_number", "cdn", "created_at", "uuid")
#     search_fields = ("title", "video_url")
#     list_filter = ("episode", "cdn")


# class ChapterViewInline(admin.TabularInline):
#     model = ChapterView
#     extra = 0
#     fields = ("chapter", "state", "unlocked_at", "watched_at", "price")
#     autocomplete_fields = ("chapter",)


# @admin.register(LibraryEntry)
# class LibraryEntryAdmin(admin.ModelAdmin):
#     list_display = ("user", "series", "episode")
#     search_fields = ("user__username", "episode__title")
#     list_filter = ("episode",)
#     inlines = [ChapterViewInline]

#     def series(self, obj):
#         return obj.episode.series

#     series.admin_order_field = "episode__series"
#     series.short_description = "Series"


# @admin.register(SeriesMarketing)
# class SeriesMarketingAdmin(admin.ModelAdmin):
#     list_display = ("series", "placement", "site", "order")
#     list_filter = ("placement", "site")
#     search_fields = ("series__title",)
#     autocomplete_fields = ("series", "site")
#     ordering = ("site", "placement", "order")


# @admin.register(SeriesStats)
# class SeriesStatsAdmin(admin.ModelAdmin):
#     list_display = ("series", "site", "views", "likes", "dislikes")
#     list_filter = ("site",)
#     search_fields = ("series__title",)
#     autocomplete_fields = ("series", "site")
#     ordering = ("site", "series")
