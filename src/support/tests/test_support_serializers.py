import datetime

from django.test import TestCase
from django.utils import timezone

from localization.models import Language
from support.api.serializers import (
    HelpArticleSerializer,
    HelpCategorySerializer,
    HelpFAQSerializer,
    _pick_translation,
)
from support.models import (
    HelpArticle,
    HelpArticleTranslation,
    HelpCategory,
    HelpCategoryTranslation,
    HelpFAQ,
    HelpFAQTranslation,
)


def make_language(code="en", name="English"):
    lang, _ = Language.objects.get_or_create(
        code=code,
        defaults={"name": name, "display_name": name, "flag": "🇺🇸"},
    )
    return lang


def make_category(slug="general", icon="help-circle", color="blue", order=1):
    return HelpCategory.objects.create(slug=slug, icon=icon, color=color, order=order)


# ── _pick_translation ─────────────────────────────────────────────────────────


class PickTranslationTests(TestCase):
    def setUp(self):
        self.en = make_language("en", "English")
        self.fr = make_language("fr", "French")
        self.cat = make_category()

    def _make_translation(self, lang, title):
        return HelpCategoryTranslation.objects.create(
            category=self.cat,
            language=lang,
            title=title,
            description="",
        )

    def test_returns_exact_language_match(self):
        self._make_translation(self.en, "English Title")
        self._make_translation(self.fr, "French Title")
        translations = list(
            HelpCategoryTranslation.objects.filter(category=self.cat).select_related(
                "language"
            )
        )
        result = _pick_translation(translations, "fr")
        self.assertEqual(result.title, "French Title")

    def test_falls_back_to_english(self):
        self._make_translation(self.en, "English Title")
        translations = list(
            HelpCategoryTranslation.objects.filter(category=self.cat).select_related(
                "language"
            )
        )
        result = _pick_translation(translations, "ja")
        self.assertEqual(result.title, "English Title")

    def test_returns_none_when_no_translations(self):
        result = _pick_translation([], "en")
        self.assertIsNone(result)


# ── HelpCategorySerializer ────────────────────────────────────────────────────


class HelpCategorySerializerTests(TestCase):
    def setUp(self):
        self.en = make_language("en")
        self.fr = make_language("fr", "French")
        self.cat = make_category(slug="streaming", icon="video", color="green")
        HelpCategoryTranslation.objects.create(
            category=self.cat,
            language=self.en,
            title="Streaming",
            description="Playback help",
        )
        HelpCategoryTranslation.objects.create(
            category=self.cat,
            language=self.fr,
            title="Diffusion",
            description="Aide lecture",
        )

    def _serialize(self, lang="en"):
        cat = HelpCategory.objects.prefetch_related("translations__language").get(
            pk=self.cat.pk
        )
        return HelpCategorySerializer(cat, context={"lang": lang}).data

    def test_id_is_slug(self):
        data = self._serialize()
        self.assertEqual(data["id"], "streaming")

    def test_includes_expected_fields(self):
        data = self._serialize()
        self.assertSetEqual(
            set(data.keys()), {"id", "title", "description", "icon", "color"}
        )

    def test_returns_english_translation(self):
        data = self._serialize("en")
        self.assertEqual(data["title"], "Streaming")

    def test_returns_french_translation(self):
        data = self._serialize("fr")
        self.assertEqual(data["title"], "Diffusion")

    def test_falls_back_to_english_for_unknown_lang(self):
        data = self._serialize("ja")
        self.assertEqual(data["title"], "Streaming")

    def test_empty_string_when_no_translation(self):
        cat2 = make_category(slug="empty-cat", order=2)
        serialized = HelpCategorySerializer(cat2, context={"lang": "en"}).data
        self.assertEqual(serialized["title"], "")


# ── HelpArticleSerializer ─────────────────────────────────────────────────────


class HelpArticleSerializerTests(TestCase):
    def setUp(self):
        self.en = make_language("en")
        self.cat = make_category()
        self.article = HelpArticle.objects.create(
            category=self.cat,
            slug="getting-started",
            read_time_minutes=5,
            is_popular=True,
            updated_at=timezone.now() - datetime.timedelta(days=3),
        )
        HelpArticleTranslation.objects.create(
            article=self.article,
            language=self.en,
            title="Getting Started",
            description="A beginner guide",
        )

    def _serialize(self, lang="en"):
        art = (
            HelpArticle.objects.prefetch_related("translations__language")
            .select_related("category")
            .get(pk=self.article.pk)
        )
        return HelpArticleSerializer(art, context={"lang": lang}).data

    def test_includes_expected_fields(self):
        data = self._serialize()
        self.assertSetEqual(
            set(data.keys()),
            {"id", "title", "description", "category", "readTime", "lastUpdated"},
        )

    def test_read_time_formatted(self):
        data = self._serialize()
        self.assertEqual(data["readTime"], "5 min")

    def test_category_is_slug(self):
        data = self._serialize()
        self.assertEqual(data["category"], self.cat.slug)

    def test_last_updated_is_human_readable(self):
        data = self._serialize()
        # Should contain a number and time unit word
        self.assertRegex(data["lastUpdated"], r"\d+\s+\w+")

    def test_translation_title_returned(self):
        data = self._serialize()
        self.assertEqual(data["title"], "Getting Started")


# ── HelpFAQSerializer ─────────────────────────────────────────────────────────


class HelpFAQSerializerTests(TestCase):
    def setUp(self):
        self.en = make_language("en")
        self.cat = make_category()
        self.faq = HelpFAQ.objects.create(category=self.cat, order=1)
        HelpFAQTranslation.objects.create(
            faq=self.faq,
            language=self.en,
            question="How do I cancel?",
            answer="Go to settings.",
        )

    def _serialize(self, lang="en"):
        faq = (
            HelpFAQ.objects.prefetch_related("translations__language")
            .select_related("category")
            .get(pk=self.faq.pk)
        )
        return HelpFAQSerializer(faq, context={"lang": lang}).data

    def test_includes_expected_fields(self):
        data = self._serialize()
        self.assertSetEqual(set(data.keys()), {"id", "question", "answer", "category"})

    def test_question_and_answer_from_translation(self):
        data = self._serialize()
        self.assertEqual(data["question"], "How do I cancel?")
        self.assertEqual(data["answer"], "Go to settings.")

    def test_category_is_slug(self):
        data = self._serialize()
        self.assertEqual(data["category"], self.cat.slug)
