# from django.contrib.auth.decorators import login_required
# from django.contrib.sites.shortcuts import get_current_site

# from django.db.models import F, Prefetch, Value
# from django.db.models.functions import Coalesce
from django.shortcuts import redirect  # , render

# from microdrama.models import SeriesMarketing, SeriesStats  # , Series

# from .forms import ProfileForm

# from django.views.generic import TemplateView


# class HomePageView(TemplateView):
#     template_name = "core/home.html"

#     # def get_context_data(self, **kwargs):
#     #     context = super().get_context_data(**kwargs)
#     #     # context["title"] = "Home"
#     #     # context["description"] = "Welcome to the home page!"
#     #     return context


# def home(request):
#     site = get_current_site(request)
#     # Query SeriesStats for this site, prefetch related Series
#     stats_qs = SeriesStats.objects.filter(site=site).select_related("series")
#     trending_stats = stats_qs.order_by("-views")[:6]
#     # Extract the related Series objects
#     trending = [stat.series for stat in trending_stats]
#     # Query SeriesMarketing for Must See for the current site
#     must_see_qs = (
#         SeriesMarketing.objects.filter(
#             placement=SeriesMarketing.Placement.MUST_SEE, site=site
#         )
#         .select_related("series")
#         .order_by("order", "id")
#     )
#     must_see = [sm.series for sm in must_see_qs]
#     # Query SeriesMarketing for Hidden Gems for the current site
#     hidden_gems_qs = (
#         SeriesMarketing.objects.filter(
#             placement=SeriesMarketing.Placement.HIDDEN_GEMS, site=site
#         )
#         .select_related("series")
#         .order_by("order", "id")
#     )
#     hidden_gems = [sm.series for sm in hidden_gems_qs]
#     # Query SeriesMarketing for Hero Section for the current site
#     hero_qs = (
#         SeriesMarketing.objects.filter(
#             placement=SeriesMarketing.Placement.HERO, site=site
#         )
#         .select_related("series")
#         .order_by("order", "id")[:3]  # max out the number of hero series at 3
#     )
#     hero_series = [sm.series for sm in hero_qs]
#     return render(
#         request,
#         "core/home.html",
#         {
#             "must_see_series": must_see,
#             "trending_series": trending,
#             "hidden_gems_series": hidden_gems,
#             "hero_series": hero_series,
#         },
#     )


# def terms(request):
#     return render(request, "core/terms.html")


# def privacy(request):
#     return render(request, "core/privacy.html")


# @login_required
# def profile(request):
#     user = request.user
#     wallet = getattr(user, "wallet", None)  # Fetch the user's wallet if it exists
#     return render(
#         request,
#         "core/profile.html",
#         {
#             "user": user,
#             "wallet_balance": (
#                 wallet.balance if wallet else 0
#             ),  # Default to 0 if no wallet
#         },
#     )


# @login_required
# def profile_edit(request):
#     user = request.user
#     if request.method == "POST":
#         form = ProfileForm(request.POST, instance=user)
#         if form.is_valid():
#             form.save()
#             return redirect("core:profile")
#     else:
#         form = ProfileForm(instance=user)
#     return render(request, "core/profile_edit.html", {"form": form})


# def about(request):
#     return render(request, "core/about.html")


def movbits_redirect(request):
    return redirect("https://www.movbits.com")
