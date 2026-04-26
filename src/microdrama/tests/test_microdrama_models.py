from django.test import TestCase

from microdrama.models import Chapter, Episode, Series
from team.models import Team

# from django.urls import reverse


class ModelsTests(TestCase):
    # def test_episode_get_absolute_url(self):
    #     team = Team.objects.create(name="Test Team", slug="test-team")
    #     series = Series.objects.create(title="Test Series", team=team)
    #     episode = Episode.objects.create(title="Test Episode", series=series)
    #     expected_url = reverse(
    #         "player",
    #         kwargs={
    #             "team": team.slug,
    #             "series": series.slug,
    #             "episode": episode.slug,
    #         },
    #     )
    #     self.assertEqual(episode.get_absolute_url(), expected_url)
    #     self.assertEqual(str(episode), "Test Episode")

    def test_chapter_str(self):
        team = Team.objects.create(name="Test Team", slug="test-team")
        series = Series.objects.create(title="Test Series", team=team)
        episode = Episode.objects.create(title="Test Episode", series=series)
        chapter = Chapter.objects.create(
            title="Test Chapter",
            episode=episode,
            chapter_number=1,
            video_url="test_url",
            cdn=1,
        )
        self.assertEqual(str(chapter), "Test Chapter")
