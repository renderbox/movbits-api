from django.contrib.auth import get_user_model
from django.test import TestCase

from localization.models import Language
from support.models import (
    HelpArticle,
    HelpArticleTranslation,
    HelpCategory,
    HelpCategoryTranslation,
    HelpFAQ,
    HelpFAQTranslation,
    SenderRole,
    SupportTicket,
    TicketAttachment,
    TicketCategory,
    TicketMessage,
    TicketPriority,
    TicketStatus,
)

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_user(username="testuser"):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="password",
    )


def make_language(code="en", name="English"):
    lang, _ = Language.objects.get_or_create(
        code=code,
        defaults={"name": name, "display_name": name, "flag": "🇺🇸"},
    )
    return lang


def make_category(slug="technical", icon="settings", color="orange", order=1):
    return HelpCategory.objects.create(slug=slug, icon=icon, color=color, order=order)


# ── Ticket model tests ────────────────────────────────────────────────────────


class SupportTicketModelTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_create_ticket_with_defaults(self):
        ticket = SupportTicket.objects.create(
            user=self.user,
            subject="Login issue",
            description="Can't log in.",
        )
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertEqual(ticket.priority, TicketPriority.MEDIUM)
        self.assertEqual(ticket.category, TicketCategory.GENERAL)
        self.assertIsNone(ticket.assigned_to)
        self.assertEqual(ticket.resolution, "")

    def test_str_includes_status_and_subject(self):
        ticket = SupportTicket.objects.create(
            user=self.user, subject="Billing error", description="Charged twice."
        )
        self.assertIn("open", str(ticket))
        self.assertIn("Billing error", str(ticket))

    def test_ordered_by_created_at_descending(self):
        t1 = SupportTicket.objects.create(
            user=self.user, subject="First", description="."
        )
        t2 = SupportTicket.objects.create(
            user=self.user, subject="Second", description="."
        )
        tickets = list(SupportTicket.objects.all())
        self.assertEqual(tickets[0], t2)
        self.assertEqual(tickets[1], t1)

    def test_assigned_to_nullable(self):
        agent = make_user("agent")
        ticket = SupportTicket.objects.create(
            user=self.user, subject="Assigned", description=".", assigned_to=agent
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.assigned_to, agent)
        ticket.assigned_to = None
        ticket.save()
        ticket.refresh_from_db()
        self.assertIsNone(ticket.assigned_to)


class TicketMessageModelTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.ticket = SupportTicket.objects.create(
            user=self.user, subject="Issue", description="Desc."
        )

    def test_create_message(self):
        msg = TicketMessage.objects.create(
            ticket=self.ticket,
            sender=self.user,
            message="Hello support.",
        )
        self.assertEqual(msg.sender_role, SenderRole.USER)
        self.assertEqual(msg.ticket, self.ticket)

    def test_str_references_ticket_and_sender(self):
        msg = TicketMessage.objects.create(
            ticket=self.ticket, sender=self.user, message="Hi."
        )
        self.assertIn(str(self.ticket.pk), str(msg))

    def test_messages_ordered_by_timestamp(self):
        m1 = TicketMessage.objects.create(
            ticket=self.ticket, sender=self.user, message="First"
        )
        m2 = TicketMessage.objects.create(
            ticket=self.ticket, sender=self.user, message="Second"
        )
        msgs = list(self.ticket.messages.all())
        self.assertEqual(msgs[0], m1)
        self.assertEqual(msgs[1], m2)


class TicketAttachmentModelTests(TestCase):
    def setUp(self):
        user = make_user()
        ticket = SupportTicket.objects.create(user=user, subject="S", description="D")
        self.message = TicketMessage.objects.create(
            ticket=ticket, sender=user, message="Msg"
        )

    def test_create_attachment(self):
        att = TicketAttachment.objects.create(
            message=self.message,
            filename="screenshot.png",
            url="https://example.com/screenshot.png",
        )
        self.assertEqual(str(att), "screenshot.png")


# ── Help Center model tests ───────────────────────────────────────────────────


class HelpCategoryModelTests(TestCase):
    def test_create_and_str(self):
        cat = make_category(slug="streaming")
        self.assertEqual(str(cat), "streaming")

    def test_ordered_by_order_field(self):
        HelpCategory.objects.create(slug="b", icon="x", color="red", order=2)
        HelpCategory.objects.create(slug="a", icon="y", color="blue", order=1)
        slugs = list(HelpCategory.objects.values_list("slug", flat=True))
        self.assertEqual(slugs, ["a", "b"])

    def test_inactive_category_is_persisted(self):
        cat = HelpCategory.objects.create(
            slug="hidden", icon="x", color="grey", order=99, is_active=False
        )
        self.assertFalse(cat.is_active)


class HelpCategoryTranslationModelTests(TestCase):
    def setUp(self):
        self.lang = make_language()
        self.cat = make_category()

    def test_create_translation(self):
        t = HelpCategoryTranslation.objects.create(
            category=self.cat,
            language=self.lang,
            title="Technical Support",
            description="Fixes and troubleshooting",
        )
        self.assertIn(self.cat.slug, str(t))
        self.assertIn(self.lang.code, str(t))

    def test_unique_together_enforced(self):
        HelpCategoryTranslation.objects.create(
            category=self.cat, language=self.lang, title="T", description="D"
        )
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            HelpCategoryTranslation.objects.create(
                category=self.cat, language=self.lang, title="T2", description="D2"
            )


class HelpArticleModelTests(TestCase):
    def setUp(self):
        self.cat = make_category()

    def test_create_article(self):
        art = HelpArticle.objects.create(
            category=self.cat,
            slug="getting-started-guide",
            read_time_minutes=5,
            is_popular=True,
        )
        self.assertEqual(str(art), "getting-started-guide")
        self.assertTrue(art.is_active)

    def test_popular_articles_sorted_first(self):
        HelpArticle.objects.create(
            category=self.cat, slug="unpopular", read_time_minutes=3, is_popular=False
        )
        HelpArticle.objects.create(
            category=self.cat, slug="popular", read_time_minutes=3, is_popular=True
        )
        slugs = list(HelpArticle.objects.values_list("slug", flat=True))
        self.assertEqual(slugs[0], "popular")


class HelpArticleTranslationModelTests(TestCase):
    def setUp(self):
        self.lang = make_language()
        self.cat = make_category()
        self.article = HelpArticle.objects.create(
            category=self.cat, slug="test-article", read_time_minutes=4
        )

    def test_create_translation(self):
        t = HelpArticleTranslation.objects.create(
            article=self.article,
            language=self.lang,
            title="Test Article",
            description="A test article description.",
        )
        self.assertIn("test-article", str(t))
        self.assertIn("en", str(t))

    def test_unique_together_enforced(self):
        HelpArticleTranslation.objects.create(
            article=self.article, language=self.lang, title="T", description="D"
        )
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            HelpArticleTranslation.objects.create(
                article=self.article, language=self.lang, title="T2", description="D2"
            )


class HelpFAQModelTests(TestCase):
    def setUp(self):
        self.lang = make_language()
        self.cat = make_category()

    def test_create_faq(self):
        faq = HelpFAQ.objects.create(category=self.cat, order=1)
        self.assertIn(str(faq.pk), str(faq))
        self.assertIn(self.cat.slug, str(faq))

    def test_ordered_by_category_then_order(self):
        cat2 = make_category(slug="account", order=2)
        HelpFAQ.objects.create(category=self.cat, order=2)
        HelpFAQ.objects.create(category=self.cat, order=1)
        HelpFAQ.objects.create(category=cat2, order=1)
        faqs = list(HelpFAQ.objects.select_related("category"))
        self.assertEqual(faqs[0].category.slug, self.cat.slug)
        self.assertEqual(faqs[0].order, 1)


class HelpFAQTranslationModelTests(TestCase):
    def setUp(self):
        self.lang = make_language()
        self.cat = make_category()
        self.faq = HelpFAQ.objects.create(category=self.cat, order=1)

    def test_create_translation(self):
        t = HelpFAQTranslation.objects.create(
            faq=self.faq,
            language=self.lang,
            question="How do I reset my password?",
            answer="Click Forgot Password on the login page.",
        )
        self.assertIn(str(self.faq.pk), str(t))
        self.assertIn("en", str(t))

    def test_unique_together_enforced(self):
        HelpFAQTranslation.objects.create(
            faq=self.faq, language=self.lang, question="Q", answer="A"
        )
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            HelpFAQTranslation.objects.create(
                faq=self.faq, language=self.lang, question="Q2", answer="A2"
            )
