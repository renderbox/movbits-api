from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Language
from .serializers import LanguageSerializer, LocalizationDataSerializer

# CONSENT_VERSION = "1.0.0"

# Session key used to store a user's language preference (dev)
_SESSION_LANG_KEY = "preferred_language"


@api_view(["GET"])
def available_languages(request):
    """
    GET /api/v1/localization/languages
    Returns AvailableLanguagesResponse:
      { languages: [{code, name, displayName, flag, rtl}], defaultLanguage: 'en' }
    """
    languages = Language.objects.filter(is_active=True)
    response = {
        "languages": LanguageSerializer(languages, many=True).data,
        "defaultLanguage": "en",
    }
    return Response(response)


class TranslationsView(APIView):
    """
    GET /api/v1/localization/translations/<language_code>

    Returns LocalizationData: { language: {...}, translations: { key: value, ... } }

    Falls back to English when the requested language code is not found or inactive.
    """

    permission_classes = []  # public — no auth required

    def get(self, request, language_code: str):
        language = (
            Language.objects.filter(code=language_code, is_active=True)
            .prefetch_related("translations")
            .first()
        )
        if not language:
            language = (
                Language.objects.filter(code="en", is_active=True)
                .prefetch_related("translations")
                .first()
            )
        if not language:
            return Response(
                {"detail": "No translations available."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = LocalizationDataSerializer(language)
        return Response(serializer.data)


@api_view(["POST"])
def set_user_language(request):
    """
    POST /api/v1/localization/set-language
    Accepts { languageCode: 'en' } (SetLanguageRequest)
    Returns SetLanguageResponse:
      { success: True, message: "...", language: { code, name } }
    """
    payload = request.data or {}
    lang_code = payload.get("languageCode")
    if not lang_code:
        return Response(
            {"success": False, "message": "languageCode is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate language exists
    language = Language.objects.filter(code=lang_code, is_active=True).first()
    if not language:
        return Response(
            {"success": False, "message": f"Language '{lang_code}' not supported"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    lang_entry = LanguageSerializer(language).data

    # Persist preference: user profile if authenticated, otherwise session
    if getattr(request, "user", None) and getattr(
        request.user, "is_authenticated", False
    ):
        request.user.preferred_language = language
        request.user.save(update_fields=["preferred_language"])
    else:
        if not request.session.session_key:
            request.session.create()
        request.session[_SESSION_LANG_KEY] = lang_code

    return Response(
        {
            "success": True,
            "message": "Language preference saved",
            "language": lang_entry,
        }
    )


@api_view(["GET"])
def get_user_language(request):
    """
    GET /api/v1/localization/user-language
    Returns { languageCode: string } — user's preferred language or default
    """
    lang_code = None

    # Authenticated users: read from profile
    if getattr(request, "user", None) and getattr(
        request.user, "is_authenticated", False
    ):
        if request.user.preferred_language_id:
            lang_code = request.user.preferred_language.code

    # Unauthenticated: fall back to session
    if not lang_code:
        if request.session.session_key:
            lang_code = request.session.get(_SESSION_LANG_KEY)

    if not lang_code:
        lang_code = "en"

    return Response({"languageCode": lang_code})
