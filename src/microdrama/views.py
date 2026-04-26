from urllib.parse import urlencode

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.contrib.sites.shortcuts import get_current_site
from django.core.files.storage import default_storage
from django.db.models import F
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_GET
from django.views.generic import DetailView, ListView

from event_machine.logging import log_event
from team.models import Team
from wallet.models import Wallet

from .mixins import SeriesAgeRequiredMixin
from .models import Chapter, ChapterView, Episode, LibraryEntry, Series, SeriesMarketing


class BaseCatalog(ListView):
    model = Series
    template_name = "microdrama/catalog.html"
    context_object_name = "series_list"

    def get_queryset(self):
        # 1) start from the default Series queryset
        qs = super().get_queryset()

        # 2) grab the current Site object
        current_site = get_current_site(self.request)

        # 3) filter to only those Series assigned to this site
        return qs.filter(sites=current_site)

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["title"] = self.title
        ctx["description"] = self.description
        return ctx


class CatalogView(BaseCatalog):
    title = "Catalog"
    description = "All Series"
    paginate_by = 24

    # define which fields are allowed for ordering (without the “-”)
    ALLOWED_ORDER_FIELDS = {"title", "created", "min_age"}

    def get_queryset(self):
        qs = super().get_queryset()

        # 1) search
        search_term = self.request.GET.get("q", "").strip()
        if search_term:
            qs = qs.filter(title__icontains=search_term)

        # 2) ordering with whitelist
        raw_order = self.request.GET.get("order", "title")
        # detect direction
        direction = "-" if raw_order.startswith("-") else ""
        field_name = raw_order.lstrip("-")
        # only allow if in whitelist, else fallback
        if field_name in self.ALLOWED_ORDER_FIELDS:
            order_by = f"{direction}{field_name}"
        else:
            order_by = "title"

        qs = qs.order_by(order_by)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_term"] = self.request.GET.get("q", "")
        ctx["current_order"] = self.request.GET.get("order", "-title")
        # expose allowed orders for template dropdown if you like
        ctx["allowed_orders"] = [
            ("-title", "Title ↓"),
            ("title", "Title ↑"),
            ("-created", "Newest first"),
            ("created", "Oldest first"),
            ("-min_age", "Lowest age ↓"),
            ("min_age", "Highest age ↑"),
        ]
        return ctx


class TrendingView(BaseCatalog):
    title = "Top Rated Series"
    description = "Our Top Picks"

    def get_queryset(self):
        # 1) start with the BaseCatalog queryset
        qs = super().get_queryset()

        # 2) limit to series that have stats on *this* site
        current_site = get_current_site(self.request)
        qs = qs.filter(sites__id=current_site.id, stats__site__id=current_site.id)

        # 3) bring in the likes count from the related SeriesStats
        qs = qs.annotate(site_likes=F("stats__likes"))

        # 4) order by that likes count, descending, and take the top 20
        return qs.order_by("-site_likes")[:20]


class TeamCatalogView(BaseCatalog):
    title = "Team Catalog"
    description = ""  # can be dynamic

    def get_queryset(self):
        team_slug = self.kwargs["team"]
        # team should be an instance of Team to get the proper name
        team = Team.objects.get(slug=team_slug)
        self.description = f"All Series by {team.name}"
        return super().get_queryset()


class MustSeeView(BaseCatalog):
    title = "Must See!"
    description = "Our Must See Microdramas"

    def get_queryset(self):
        current_site = get_current_site(self.request)
        # Get SeriesMarketing for MUST_SEE placement, ordered
        must_see_qs = (
            SeriesMarketing.objects.filter(
                placement=SeriesMarketing.Placement.MUST_SEE,
                site=current_site,
            )
            .select_related("series")
            .order_by("order", "series__title")
        )
        # Return the related Series objects in order
        return [sm.series for sm in must_see_qs]


class HiddenGemsView(BaseCatalog):
    title = "Hidden Gems"
    description = "Our Hidden Gems Picks"

    def get_queryset(self):
        current_site = get_current_site(self.request)
        hidden_gems_qs = (
            SeriesMarketing.objects.filter(
                placement=SeriesMarketing.Placement.HIDDEN_GEMS,
                site=current_site,
            )
            .select_related("series")
            .order_by("order", "series__title")
        )
        return [sm.series for sm in hidden_gems_qs]


class SeriesDetailView(SeriesAgeRequiredMixin, DetailView):
    model = Series
    template_name = "microdrama/series_detail.html"
    context_object_name = "series"

    # which URL kwarg holds the series slug
    slug_url_kwarg = "series"
    slug_field = "slug"

    def get_queryset(self):
        # restrict to the given team
        return super().get_queryset().filter(team__slug=self.kwargs["team"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # grab all episodes for this series in order
        ctx["episodes"] = self.object.episodes.all().order_by("order")
        return ctx


class PlayerView(SeriesAgeRequiredMixin, DetailView):
    """
    View for playing an episode of a series.
    """

    model = Episode
    template_name = "microdrama/player.html"
    context_object_name = "episode"
    slug_field = "slug"
    slug_url_kwarg = "episode"

    def get_queryset(self):
        """
        Only allow episodes matching both the series and the team from the URL.
        DetailView will then pull the one whose slug matches `episode`.
        """
        return (
            super()
            .get_queryset()
            .filter(
                series__slug=self.kwargs["series"],
                series__team__slug=self.kwargs["team"],
            )
        )

    def post(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path())

        self.object = self.get_object()
        chapter_number = self.kwargs.get("chapter")
        chapters = list(self.object.chapters.all().order_by("chapter_number"))
        selected_chapter = next(
            (c for c in chapters if c.chapter_number == chapter_number), None
        )
        if not selected_chapter:
            messages.error(request, "Chapter not found.")
            return redirect(request.path)

        # Only unlock if a paid chapter
        if selected_chapter.free:
            messages.info(request, "This chapter is already free.")
            return redirect(request.path)

        # Get or create LibraryEntry
        library_entry, created = LibraryEntry.objects.get_or_create(
            user=user, episode=self.object
        )

        # Log the event when a new chapter is unlocked
        log_event(
            "chapter_unlock",  # group
            user.id,  # user_id
            request=request,  # Pass the request object
            episode_id=self.object.id,
            chapter_number=chapter_number,
        )

        # If the session has a referral_episode_id set, and it's the current episode,
        # then link the referral to the library entry
        referral_episode_id = request.session.get("referral_episode_id")
        if referral_episode_id == self.object.id and created:
            library_entry.referral_id = request.session.get("referral_id")
            library_entry.save()

            # Log the event when a referral is used to add the episode to the user's library
            log_event(
                "referral_used",  # group
                user.id,  # user_id
                request=request,  # Pass the request object
                episode_id=self.object.id,
                referral_id=request.session.get("referral_id"),
            )

            # Remove referral keys from session
            request.session.pop("referral_episode_id", None)
            request.session.pop("referral_id", None)

        # Check if already unlocked
        chapter_view, created = ChapterView.objects.get_or_create(
            library=library_entry, chapter=selected_chapter
        )
        if not created and chapter_view.state != ChapterView.ChapterState.LOCKED:
            messages.info(request, "Chapter already unlocked.")
            return redirect(request.path)

        # Check wallet
        wallet, _ = Wallet.objects.get_or_create(
            user=user, site=request.site, credit_type=Wallet.CreditTypes.CREDIT
        )  # we will create a wallet if one doesn't exist, but it will start with 0 balance, so the user will just get a "not enough credits" message and be prompted to add funds  # noqa: E501

        price = self.object.price
        if wallet.balance < price:
            messages.error(
                request,
                f"Not enough credits to unlock this chapter. You need {price} credits.",
            )
            add_funds_url = reverse("virtcurrency:add_funds")
            next_url = request.get_full_path()
            return redirect(f"{add_funds_url}?{urlencode({'next': next_url})}")

        # Deduct credits and unlock
        wallet.balance -= price
        wallet.save()
        chapter_view.state = ChapterView.ChapterState.PAID_UNWATCHED
        chapter_view.unlocked_at = chapter_view.unlocked_at or timezone.now()
        chapter_view.price = price
        chapter_view.save()
        messages.success(request, "Chapter unlocked!")
        return redirect(request.path)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        chapter_number = self.kwargs.get("chapter")
        selected_chapter = None
        chapters = list(self.object.chapters.all().order_by("chapter_number"))

        library_entry = None
        watched_chapter_numbers = set()
        if user.is_authenticated:
            library_entry, created = LibraryEntry.objects.get_or_create(
                user=user, episode=self.object
            )
            watched = getattr(library_entry, "watched_chapter_indexes", lambda: [])()
            watched_chapter_numbers = set(watched)

        if chapter_number is not None:
            selected_chapter = next(
                (c for c in chapters if c.chapter_number == chapter_number), None
            )
        else:
            if user.is_authenticated and library_entry:
                if watched_chapter_numbers:
                    selected_chapter = next(
                        (
                            c
                            for c in chapters
                            if c.chapter_number == list(watched_chapter_numbers)[-1]
                        ),
                        None,
                    )
            if not selected_chapter and chapters:
                selected_chapter = chapters[0]

        context["selected_chapter"] = selected_chapter

        # Check if selected chapter is locked for this user
        is_locked = False
        if user.is_authenticated and library_entry and selected_chapter:
            chapter_view = ChapterView.objects.filter(
                library=library_entry, chapter=selected_chapter
            ).first()
            if not selected_chapter.free and (
                not chapter_view
                or chapter_view.state == ChapterView.ChapterState.LOCKED
            ):
                is_locked = True
        elif selected_chapter and not selected_chapter.free:
            is_locked = True
        context["is_locked"] = is_locked
        context["chapter_price"] = self.object.price

        # Build chapter state list for template
        chapter_states = []
        for chapter in chapters:
            style = None
            chapter_view_state = None
            if user.is_authenticated and library_entry:
                chapter_view = ChapterView.objects.filter(
                    library=library_entry, chapter=chapter
                ).first()
                if chapter_view:
                    chapter_view_state = chapter_view.state
            if chapter.free:
                style = "free"
            elif not chapter.free:
                if chapter_view_state == ChapterView.ChapterState.PAID_UNWATCHED:
                    style = "paid"
                elif (
                    chapter_view_state == ChapterView.ChapterState.LOCKED
                    or chapter_view_state is None
                ):
                    style = "locked"
            if selected_chapter and chapter.pk == selected_chapter.pk:
                style = f"{style} selected" if style else "selected"
            chapter_states.append(
                {
                    "number": chapter.chapter_number,
                    "url": chapter.get_absolute_url,
                    "style": style,
                }
            )
        context["chapter_states"] = chapter_states
        return context


@require_GET
def serve_signed_playlist(request, uuid, filename):
    try:
        chapter = Chapter.objects.get(uuid=uuid, cdn=Chapter.CDNChoices.S3_MEDIA_BUCKET)
    except Chapter.DoesNotExist:
        if settings.DEBUG:
            print(
                f"Chapter not found: uuid={uuid}, cdn={Chapter.CDNChoices.S3_MEDIA_BUCKET}"
            )
        raise Http404("Chapter not found")

    hls_dir = chapter.get_hls_dir()
    playlist_path = hls_dir + filename

    if settings.DEBUG:
        print(f"Constructed playlist path: {playlist_path}")

    try:
        playlist_file = default_storage.open(playlist_path)
        content = playlist_file.read().decode("utf-8")
    except Exception as e:
        if settings.DEBUG:
            print(f"Error opening playlist file: {e}")
        raise Http404("Playlist not found")

    signed_lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.endswith(".ts"):
            signed_url = default_storage.url(hls_dir + stripped)
            signed_lines.append(signed_url)
        elif stripped.endswith(".m3u8"):
            signed_lines.append(reverse("hls_url", args=[uuid, stripped]))
        else:
            signed_lines.append(line)

    if settings.DEBUG:
        print(f"Serving signed playlist for {filename} with {len(signed_lines)} lines")
        print("\n".join(signed_lines))

    return HttpResponse(
        "\n".join(signed_lines), content_type="application/vnd.apple.mpegurl"
    )


class EnterDOBForm(forms.Form):
    date_of_birth = forms.DateField(
        label="Date of Birth",
        widget=forms.DateInput(attrs={"type": "date"}),
        input_formats=["%Y-%m-%d"],
    )


@method_decorator(login_required, name="dispatch")
class EnterDOBView(View):
    template_name = "microdrama/enter_dob.html"
    form_class = EnterDOBForm
    success_url = reverse_lazy("catalog")  # Change to your desired redirect

    def get(self, request, *args, **kwargs):
        form = self.form_class()
        return render(request, self.template_name, {"form": form})

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        if form.is_valid():
            dob = form.cleaned_data["date_of_birth"]
            user = request.user
            user.date_of_birth = dob
            user.save()
            return redirect(self.success_url)
        return render(request, self.template_name, {"form": form})
