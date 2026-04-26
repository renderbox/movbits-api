from django.contrib.sites.models import Site
from django.db.utils import IntegrityError
from django.test import TestCase
from django.utils.text import slugify

from shortlink.models import ReferralLink
from shows.models import Show
from team.models import Team


def make_show(title="Test Show", team=None):
    site, _ = Site.objects.get_or_create(
        id=1, defaults={"domain": "example.com", "name": "example"}
    )
    if team is None:
        team, _ = Team.objects.get_or_create(name="Default Team", slug="default-team")
    return Show.objects.create(title=title, team=team, site=site)


class ReferralLinkModelTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team", slug="test-team")
        self.show = make_show(team=self.team)
        self.referral = ReferralLink.objects.create(
            show=self.show, name="Test Referral"
        )

    def test_str_method(self):
        self.assertEqual(
            str(self.referral), f"Referral for {self.show.title} — Test Referral"
        )

    def test_save_generates_slug_from_name(self):
        referral = ReferralLink.objects.create(show=self.show, name="New Referral Link")
        self.assertEqual(referral.slug, "new-referral-link")

    def test_save_sanitises_slug_with_spaces(self):
        referral = ReferralLink.objects.create(
            show=self.show, name="Bad Slug", slug="bad slug"
        )
        self.assertEqual(referral.slug, slugify("bad slug"))

    def test_soft_delete_sets_deleted_flag(self):
        self.referral.delete()
        self.referral.refresh_from_db()
        self.assertTrue(self.referral.deleted)

    def test_soft_delete_does_not_remove_row(self):
        pk = self.referral.pk
        self.referral.delete()
        self.assertTrue(ReferralLink.objects.filter(pk=pk).exists())

    def test_defaults(self):
        self.assertEqual(self.referral.link_type, "shared")
        self.assertEqual(self.referral.cta_text, "Learn More")
        self.assertTrue(self.referral.enabled)
        self.assertFalse(self.referral.deleted)
        self.assertEqual(self.referral.click_count, 0)
        self.assertEqual(self.referral.assigned_email, "")

    def test_duplicate_slug_raises(self):
        ReferralLink.objects.create(show=self.show, name="First", slug="fixed-slug")
        with self.assertRaises(IntegrityError):
            ReferralLink.objects.create(
                show=self.show, name="Second", slug="fixed-slug"
            )

    def test_missing_show_raises(self):
        with self.assertRaises(IntegrityError):
            ReferralLink.objects.create(name="No Show")
