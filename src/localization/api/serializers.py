from rest_framework import serializers

from ..models import Language


class LanguageSerializer(serializers.ModelSerializer):
    displayName = serializers.CharField(source="display_name")
    rtl = serializers.BooleanField(source="is_rtl")

    class Meta:
        model = Language
        fields = ["code", "name", "displayName", "flag", "rtl"]


class LocalizationDataSerializer(serializers.ModelSerializer):
    """
    Serialises a Language instance together with its full translation map.

    Response shape (matches the frontend LocalizationData type):
      {
        "language": { "code", "name", "displayName", "flag", "rtl" },
        "translations": { "<key>": "<value>", ... }
      }
    """

    language = serializers.SerializerMethodField()
    translations = serializers.SerializerMethodField()

    class Meta:
        model = Language
        fields = ["language", "translations"]

    def get_language(self, obj):
        return LanguageSerializer(obj).data

    def get_translations(self, obj):
        # Translations are prefetched by the view — no extra query here.
        return {t.key: t.value for t in obj.translations.all()}
