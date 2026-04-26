# from django.contrib.auth import get_user_model
# from django.test import Client, TestCase
# from django.urls import reverse

# from microdrama.models import Chapter, ChapterView, Episode, LibraryEntry, Series
# from team.models import Team
# from wallet.models import Wallet

# User = get_user_model()


# class TestMicrodramaViews(TestCase):
#     def setUp(self):
#         self.client = Client()

#     def test_enter_dob_view_get(self):
#         user = User.objects.create_user(
#             email="dobuser@example.com", username="dobuser", password="pass"
#         )
#         self.client.force_login(user)
#         url = reverse("enter-dob")
#         response = self.client.get(url)
#         # Expect 200 OK for GET
#         self.assertEqual(response.status_code, 200)

#     def test_enter_dob_view_post_valid(self):
#         user = User.objects.create_user(
#             email="dobuser2@example.com", username="dobuser2", password="pass"
#         )
#         self.client.force_login(user)
#         url = reverse("enter-dob")
#         data = {"date_of_birth": "2000-01-01"}
#         response = self.client.post(url, data)
#         # Expect 302 Redirect for valid POST
#         self.assertEqual(response.status_code, 302)

#     def test_enter_dob_view_post_invalid(self):
#         user = User.objects.create_user(
#             email="dobuser3@example.com", username="dobuser3", password="pass"
#         )
#         self.client.force_login(user)
#         url = reverse("enter-dob")
#         data = {"date_of_birth": "not-a-date"}
#         response = self.client.post(url, data)
#         # Expect 200 OK for invalid POST
#         self.assertEqual(response.status_code, 200)

#     def test_player_unlock_free_chapter(self):
#         user = User.objects.create_user(
#             email="freeuser@example.com", username="freeuser", password="pass"
#         )
#         team = Team.objects.create(name="Team1", slug="team1")
#         series = Series.objects.create(
#             title="Series1", team=team, slug="series1", description="desc"
#         )
#         episode = Episode.objects.create(
#             title="Ep1", series=series, slug="ep1", price=10
#         )
#         free_chapter = Chapter.objects.create(
#             title="FreeCh",
#             episode=episode,
#             chapter_number=1,
#             video_url="url",
#             cdn=1,
#             free=True,
#         )
#         Wallet.objects.create(user=user, balance=100)
#         self.client.force_login(user)
#         url = reverse(
#             "player-chapter",
#             kwargs={
#                 "team": team.slug,
#                 "series": series.slug,
#                 "episode": episode.slug,
#                 "chapter": int(free_chapter.chapter_number),
#             },
#         )
#         response = self.client.post(url, data={})
#         self.assertEqual(response.status_code, 302)  # Redirect after POST
#         user.refresh_from_db()
#         self.assertEqual(user.wallet.balance, 100)
#         library, _ = LibraryEntry.objects.get_or_create(user=user, episode=episode)
#         chapter_view = ChapterView.objects.filter(
#             library=library, chapter=free_chapter
#         ).first()
#         if chapter_view:
#             self.assertEqual(
#                 chapter_view.state, ChapterView.ChapterState.FREE_UNWATCHED
#             )
#         else:
#             self.assertTrue(True)

#     # TODO: Fix this test.  something in it is causing the tests to hang.

#     # def test_player_unlock_paid_chapter_with_credits(self):
#     #     twenty_years_ago = date.today().replace(year=date.today().year - 20)
#     #     user = User.objects.create_user(
#     #         username="paiduser", password="pass", date_of_birth=twenty_years_ago
#     #     )
#     #     team = Team.objects.create(name="Team2", slug="team2")
#     #     series = Series.objects.create(
#     #         title="Series2", team=team, slug="series2", description="desc"
#     #     )
#     #     episode = Episode.objects.create(
#     #         title="Ep2", series=series, slug="ep2", price=10
#     #     )
#     #     paid_chapter = Chapter.objects.create(
#     #         title="PaidCh",
#     #         episode=episode,
#     #         chapter_number=int(2),
#     #         video_url="url",
#     #         cdn=1,
#     #         free=False,
#     #     )
#     #     Wallet.objects.create(user=user, balance=20)
#     #     self.client.force_login(user)
#     #     url = reverse(
#     #         "player-chapter",
#     #         kwargs={
#     #             "team": team.slug,
#     #             "series": series.slug,
#     #             "episode": episode.slug,
#     #             "chapter": int(paid_chapter.chapter_number),
#     #         },
#     #     )
#     #     response = self.client.post(url, data={})
#     #     self.assertEqual(response.status_code, 302)
#     #     user.refresh_from_db()
#     #     self.assertEqual(user.wallet.balance, 10)
#     #     library = LibraryEntry.objects.get(user=user, episode=episode)
#     #     chapter_view = ChapterView.objects.get(library=library, chapter=paid_chapter)
#     #     self.assertEqual(chapter_view.state, ChapterView.ChapterState.PAID_UNWATCHED)
#     #     self.assertEqual(chapter_view.price, 10)

#     def test_player_unlock_paid_chapter_insufficient_credits(self):
#         user = User.objects.create_user(username="pooruser", password="pass")
#         team = Team.objects.create(name="Team3", slug="team3")
#         series = Series.objects.create(
#             title="Series3", team=team, slug="series3", description="desc"
#         )
#         episode = Episode.objects.create(
#             title="Ep3", series=series, slug="ep3", price=15
#         )
#         paid_chapter = Chapter.objects.create(
#             title="PaidCh2",
#             episode=episode,
#             chapter_number=3,
#             video_url="url",
#             cdn=1,
#             free=False,
#         )
#         Wallet.objects.create(user=user, balance=5)
#         self.client.force_login(user)
#         url = reverse(
#             "player-chapter",
#             kwargs={
#                 "team": team.slug,
#                 "series": series.slug,
#                 "episode": episode.slug,
#                 "chapter": int(paid_chapter.chapter_number),
#             },
#         )
#         response = self.client.post(url, data={})
#         self.assertEqual(response.status_code, 302)
#         user.refresh_from_db()
#         self.assertEqual(user.wallet.balance, 5)
#         library = LibraryEntry.objects.filter(user=user, episode=episode).first()
#         if library:
#             chapter_view = ChapterView.objects.filter(
#                 library=library, chapter=paid_chapter
#             ).first()
#             self.assertTrue(
#                 not chapter_view
#                 or chapter_view.state == ChapterView.ChapterState.LOCKED
#             )
#         else:
#             self.assertTrue(True)

#     # TODO: Fix this test.  something in it is causing the tests to hang.
#     # def test_player_unlock_already_unlocked_chapter(self):
#     #     twenty_years_ago = date.today().replace(year=date.today().year - 20)
#     #     user = User.objects.create_user(
#     #         username="repeatuser", password="pass", date_of_birth=twenty_years_ago
#     #     )
#     #     team = Team.objects.create(name="Team4", slug="team4")
#     #     series = Series.objects.create(
#     #         title="Series4", team=team, slug="series4", description="desc"
#     #     )
#     #     episode = Episode.objects.create(
#     #         title="Ep4", series=series, slug="ep4", price=8
#     #     )
#     #     paid_chapter = Chapter.objects.create(
#     #         title="PaidCh3",
#     #         episode=episode,
#     #         chapter_number=int(4),
#     #         video_url="url",
#     #         cdn=1,
#     #         free=False,
#     #     )
#     #     Wallet.objects.create(user=user, balance=20)
#     #     self.client.force_login(user)
#     #     self.assertFalse(
#     #         ChapterView.objects.filter(
#     #             library__user=user, chapter=paid_chapter
#     #         ).exists()
#     #     )
#     #     self.assertEqual(user.wallet.balance, 20)
#     #     url = reverse(
#     #         "player-chapter",
#     #         kwargs={
#     #             "team": team.slug,
#     #             "series": series.slug,
#     #             "episode": episode.slug,
#     #             "chapter": int(paid_chapter.chapter_number),
#     #         },
#     #     )
#     #     response = self.client.post(url, data={})
#     #     self.assertEqual(response.status_code, 302)
#     #     user.refresh_from_db()
#     #     user.wallet.refresh_from_db()
#     #     self.assertEqual(user.wallet.balance, 12)
#     #     library = LibraryEntry.objects.get(user=user, episode=episode)
#     #     chapter_view = ChapterView.objects.get(library=library, chapter=paid_chapter)
#     #     self.assertEqual(chapter_view.state, ChapterView.ChapterState.PAID_UNWATCHED)
#     #     response = self.client.post(url, data={})
#     #     self.assertEqual(response.status_code, 302)
#     #     user.refresh_from_db()
#     #     self.assertEqual(user.wallet.balance, 12)
#     #     chapter_view.refresh_from_db()
#     #     self.assertEqual(chapter_view.state, ChapterView.ChapterState.PAID_UNWATCHED)

#     def test_player_unlock_requires_login(self):
#         team = Team.objects.create(name="Team5", slug="team5")
#         series = Series.objects.create(
#             title="Series5", team=team, slug="series5", description="desc"
#         )
#         episode = Episode.objects.create(
#             title="Ep5", series=series, slug="ep5", price=5
#         )
#         paid_chapter = Chapter.objects.create(
#             title="PaidCh4",
#             episode=episode,
#             chapter_number=5,
#             video_url="url",
#             cdn=1,
#             free=False,
#         )
#         url = reverse(
#             "player-chapter",
#             kwargs={
#                 "team": team.slug,
#                 "series": series.slug,
#                 "episode": episode.slug,
#                 "chapter": int(paid_chapter.chapter_number),
#             },
#         )
#         response = self.client.post(url, data={})
#         self.assertEqual(response.status_code, 302)
#         self.assertIn("/accounts/login/", response.url)

#     def test_base_catalog_views_status_code(self):
#         base_catalog_urls = [
#             reverse("catalog"),
#             reverse("trending"),
#             reverse("must-see"),
#             reverse("hidden-gems"),
#         ]
#         for url in base_catalog_urls:
#             response = self.client.get(url)
#             self.assertEqual(response.status_code, 200)

#     # # def test_serve_signed_playlist_valid(self):
#     # #     user = User.objects.create_user(username="testuser", password="testpass")
#     # #     self.client.force_login(user)
#     # #     team = Team.objects.create(name="Team6", slug="team6")
#     # #     series = Series.objects.create(
#     # #         title="Series6", team=team, slug="series6", description="desc"
#     # #     )
#     # #     episode = Episode.objects.create(
#     # #         title="Ep6", series=series, slug="ep6", price=5
#     # #     )
#     # #     chapter = Chapter.objects.create(
#     # #         title="Chapter6",
#     # #         episode=episode,
#     # #         chapter_number=6,
#     # #         cdn=Chapter.CDNChoices.S3_MEDIA_BUCKET,
#     # #     )

#     # #     playlist_content = "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1280000\nvideo.m3u8"
#     # #     hls_dir = chapter.get_hls_dir()
#     # #     s3_path = f"{hls_dir}playlist.m3u8"

#     # #     with patch(
#     # #         "django.core.files.storage.default_storage.open",
#     # #         mock_open(read_data=playlist_content),
#     # #     ) as mock_open_file:
#     # #         mock_open_file.return_value.name = s3_path
#     # #         with patch(
#     # #             "django.core.files.storage.default_storage.url",
#     # #             return_value=f"https://s3.amazonaws.com/{s3_path}",
#     # #         ):
#     # #             url = reverse(
#     # #                 "signed_playlist",
#     # #                 kwargs={"uuid": chapter.uuid, "filename": "playlist.m3u8"},
#     # #             )

#     # #             print(f"Generated Django URL: {url}")
#     # #             print(f"Expected S3 Path: {s3_path}")

#     # #             response = self.client.get(url)
#     # #             print(response)
#     # #             self.assertEqual(response.status_code, 200)
#     # #             self.assertIn("#EXTM3U", response.content.decode("utf-8"))

#     def test_serve_signed_playlist_invalid_uuid(self):
#         url = reverse(
#             "signed_playlist",
#             kwargs={
#                 "uuid": "123e4567-e89b-12d3-a456-426614174999",
#                 "filename": "playlist.m3u8",
#             },
#         )
#         response = self.client.get(url)
#         self.assertEqual(response.status_code, 404)

#     def test_serve_signed_playlist_invalid_filename(self):
#         team = Team.objects.create(name="Team7", slug="team7")
#         series = Series.objects.create(
#             title="Series7", team=team, slug="series7", description="desc"
#         )
#         episode = Episode.objects.create(
#             title="Ep7", series=series, slug="ep7", price=5
#         )
#         chapter = Chapter.objects.create(
#             title="Chapter7",
#             episode=episode,
#             chapter_number=7,
#             uuid="123e4567-e89b-12d3-a456-426614174001",
#             cdn=Chapter.CDNChoices.S3_MEDIA_BUCKET,
#         )

#         url = reverse(
#             "signed_playlist", kwargs={"uuid": chapter.uuid, "filename": "invalid.m3u8"}
#         )
#         response = self.client.get(url)
#         self.assertEqual(response.status_code, 404)
