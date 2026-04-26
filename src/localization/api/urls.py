from django.urls import path

from . import views

urlpatterns = [
    path(
        "languages",
        views.available_languages,
        name="localization_languages",
    ),
    path(
        "translations/<str:language_code>",
        views.TranslationsView.as_view(),
        name="localization_translations",
    ),
    path(
        "set-language",
        views.set_user_language,
        name="localization_set_language",
    ),
    path(
        "user-language",
        views.get_user_language,
        name="localization_user_language",
    ),
]
