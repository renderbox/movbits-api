from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from localization.models import Language
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


def make_category(
    slug="general", icon="help-circle", color="blue", order=1, is_active=True
):
    return HelpCategory.objects.create(
        slug=slug, icon=icon, color=color, order=order, is_active=is_active
    )


def add_category_translation(category, lang, title="Title", description="Desc"):
    return HelpCategoryTranslation.objects.create(
        category=category, language=lang, title=title, description=description
    )


def make_article(category, slug, read_time_minutes=3, is_popular=False, is_active=True):
    return HelpArticle.objects.create(
        category=category,
        slug=slug,
        read_time_minutes=read_time_minutes,
        is_popular=is_popular,
        is_active=is_active,
    )


def add_article_translation(
    article, lang, title="Article Title", description="Article Desc"
):
    return HelpArticleTranslation.objects.create(
        article=article, language=lang, title=title, description=description
    )


def make_faq(category, order=1, is_active=True):
    return HelpFAQ.objects.create(category=category, order=order, is_active=is_active)


def add_faq_translation(faq, lang, question="Q?", answer="A."):
    return HelpFAQTranslation.objects.create(
        faq=faq, language=lang, question=question, answer=answer
    )


# ── HelpCategoriesView ────────────────────────────────────────────────────────


class HelpCategoriesViewTests(APITestCase):
    def setUp(self):
        self.en = make_language("en")
        self.fr = make_language("fr", "French")
        self.cat = make_category(slug="streaming")
        add_category_translation(
            self.cat, self.en, title="Streaming", description="Playback help"
        )
        add_category_translation(
            self.cat, self.fr, title="Diffusion", description="Aide lecture"
        )

    def test_public_access_without_auth(self):
        response = self.client.get(reverse("help_categories"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_shape(self):
        response = self.client.get(reverse("help_categories"))
        self.assertIn("categories", response.data)
        self.assertIn("language", response.data)

    def test_returns_active_categories(self):
        response = self.client.get(reverse("help_categories"))
        slugs = [c["id"] for c in response.data["categories"]]
        self.assertIn("streaming", slugs)

    def test_excludes_inactive_categories(self):
        make_category(slug="hidden", order=99, is_active=False)
        response = self.client.get(reverse("help_categories"))
        slugs = [c["id"] for c in response.data["categories"]]
        self.assertNotIn("hidden", slugs)

    def test_english_translation_by_default(self):
        response = self.client.get(reverse("help_categories"))
        cat = response.data["categories"][0]
        self.assertEqual(cat["title"], "Streaming")

    def test_french_translation_with_lang_param(self):
        response = self.client.get(reverse("help_categories") + "?lang=fr")
        cat = response.data["categories"][0]
        self.assertEqual(cat["title"], "Diffusion")
        self.assertEqual(response.data["language"], "fr")

    def test_falls_back_to_english_for_unknown_lang(self):
        response = self.client.get(reverse("help_categories") + "?lang=ja")
        cat = response.data["categories"][0]
        self.assertEqual(cat["title"], "Streaming")


# ── HelpArticlesView ──────────────────────────────────────────────────────────


class HelpArticlesViewTests(APITestCase):
    def setUp(self):
        self.en = make_language("en")
        self.fr = make_language("fr", "French")
        self.cat1 = make_category(slug="streaming", order=1)
        self.cat2 = make_category(slug="account", order=2)
        self.article1 = make_article(self.cat1, "video-quality", is_popular=True)
        self.article2 = make_article(self.cat2, "billing-help", is_popular=False)
        self.article_inactive = make_article(self.cat1, "old-article", is_active=False)
        add_article_translation(
            self.article1, self.en, title="Video Quality", description="Tips"
        )
        add_article_translation(
            self.article1, self.fr, title="Qualité Vidéo", description="Conseils"
        )
        add_article_translation(
            self.article2, self.en, title="Billing Help", description="Billing"
        )

    def test_public_access_without_auth(self):
        response = self.client.get(reverse("help_articles"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_shape(self):
        response = self.client.get(reverse("help_articles"))
        self.assertIn("articles", response.data)
        self.assertIn("language", response.data)

    def test_returns_active_articles_only(self):
        response = self.client.get(reverse("help_articles"))
        slugs = [a["id"] for a in response.data["articles"]]
        self.assertNotIn(self.article_inactive.pk, slugs)

    def test_article_fields(self):
        response = self.client.get(reverse("help_articles"))
        article = next(
            a for a in response.data["articles"] if a["id"] == self.article1.pk
        )
        self.assertIn("title", article)
        self.assertIn("description", article)
        self.assertIn("category", article)
        self.assertIn("readTime", article)
        self.assertIn("lastUpdated", article)

    def test_category_filter(self):
        response = self.client.get(reverse("help_articles") + "?category=streaming")
        slugs = [a["id"] for a in response.data["articles"]]
        self.assertIn(self.article1.pk, slugs)
        self.assertNotIn(self.article2.pk, slugs)

    def test_popular_filter(self):
        response = self.client.get(reverse("help_articles") + "?popular=true")
        ids = [a["id"] for a in response.data["articles"]]
        self.assertIn(self.article1.pk, ids)
        self.assertNotIn(self.article2.pk, ids)

    def test_french_translation(self):
        response = self.client.get(reverse("help_articles") + "?lang=fr")
        article = next(
            a for a in response.data["articles"] if a["id"] == self.article1.pk
        )
        self.assertEqual(article["title"], "Qualité Vidéo")

    def test_english_fallback_for_unknown_lang(self):
        response = self.client.get(reverse("help_articles") + "?lang=ja")
        article = next(
            a for a in response.data["articles"] if a["id"] == self.article1.pk
        )
        self.assertEqual(article["title"], "Video Quality")


# ── HelpFAQsView ──────────────────────────────────────────────────────────────


class HelpFAQsViewTests(APITestCase):
    def setUp(self):
        self.en = make_language("en")
        self.fr = make_language("fr", "French")
        self.cat1 = make_category(slug="streaming", order=1)
        self.cat2 = make_category(slug="account", order=2)
        self.faq1 = make_faq(self.cat1, order=1)
        self.faq2 = make_faq(self.cat2, order=1)
        self.faq_inactive = make_faq(self.cat1, order=99, is_active=False)
        add_faq_translation(
            self.faq1, self.en, question="How to stream?", answer="Press play."
        )
        add_faq_translation(
            self.faq1, self.fr, question="Comment diffuser?", answer="Appuyez sur play."
        )
        add_faq_translation(
            self.faq2, self.en, question="How to cancel?", answer="Go to settings."
        )

    def test_public_access_without_auth(self):
        response = self.client.get(reverse("help_faqs"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_shape(self):
        response = self.client.get(reverse("help_faqs"))
        self.assertIn("faqs", response.data)
        self.assertIn("language", response.data)

    def test_returns_active_faqs_only(self):
        response = self.client.get(reverse("help_faqs"))
        ids = [f["id"] for f in response.data["faqs"]]
        self.assertNotIn(self.faq_inactive.pk, ids)

    def test_faq_fields(self):
        response = self.client.get(reverse("help_faqs"))
        faq = next(f for f in response.data["faqs"] if f["id"] == self.faq1.pk)
        self.assertIn("question", faq)
        self.assertIn("answer", faq)
        self.assertIn("category", faq)

    def test_category_filter(self):
        response = self.client.get(reverse("help_faqs") + "?category=streaming")
        ids = [f["id"] for f in response.data["faqs"]]
        self.assertIn(self.faq1.pk, ids)
        self.assertNotIn(self.faq2.pk, ids)

    def test_french_translation(self):
        response = self.client.get(reverse("help_faqs") + "?lang=fr")
        faq = next(f for f in response.data["faqs"] if f["id"] == self.faq1.pk)
        self.assertEqual(faq["question"], "Comment diffuser?")

    def test_english_fallback_for_unknown_lang(self):
        response = self.client.get(reverse("help_faqs") + "?lang=ja")
        faq = next(f for f in response.data["faqs"] if f["id"] == self.faq1.pk)
        self.assertEqual(faq["question"], "How to stream?")
