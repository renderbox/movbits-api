# from django.contrib import messages
# from django.contrib.auth import get_user_model
# from django.contrib.auth.mixins import LoginRequiredMixin
# from django.core.mail import send_mail
# from django.db import IntegrityError
# from django.http import HttpResponseRedirect
# from django.shortcuts import get_object_or_404, redirect, render
# from django.urls import reverse
# from django.utils import timezone
# from django.views.generic import ListView, TemplateView, View

# from microdrama.models import Episode, Series
# from shortlink.models import ReferralLink

# from .models import Team, TeamInvite, TeamMembership

# User = get_user_model()


# class TeamMembershipMixin:
#     def get_team_and_membership(self):
#         team_slug = self.kwargs.get("team_slug")
#         team = get_object_or_404(Team, slug=team_slug)
#         user_membership = TeamMembership.objects.filter(
#             user=self.request.user, team=team
#         ).first()
#         return team, user_membership

#     def check_membership_or_redirect(self):
#         team, user_membership = self.get_team_and_membership()
#         if not user_membership or not self.request.user.is_superuser:
#             return HttpResponseRedirect(
#                 reverse("team-catalog", kwargs={"team": self.kwargs.get("team_slug")})
#             )
#         return team, user_membership

#     def get_menu_items(self, team):
#         current_page = self.request.resolver_match.url_name
#         return [
#             {
#                 "name": "Overview",
#                 "url": reverse("team-overview", kwargs={"team_slug": team.slug}),
#                 "active": current_page == "team-overview",
#             },
#             {
#                 "name": "Members",
#                 "url": reverse("team-members", kwargs={"team_slug": team.slug}),
#                 "active": current_page == "team-members",
#             },
#             {
#                 "name": "Content",
#                 "url": reverse("team-content", kwargs={"team_slug": team.slug}),
#                 "active": current_page == "team-content",
#             },
#             {
#                 "name": "Referral Links",
#                 "url": reverse("team-shortlinks", kwargs={"team_slug": team.slug}),
#                 "active": current_page == "team-shortlinks",
#             },
#         ]

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         team, user_membership = self.get_team_and_membership()
#         context.update(
#             {
#                 "team": team,
#                 "user_membership": user_membership,
#                 "is_member": bool(user_membership),
#                 "menu_items": self.get_menu_items(team) if user_membership else None,
#                 "series_list": (
#                     Series.objects.filter(team=team, active=True)
#                     if not user_membership
#                     else None
#                 ),
#             }
#         )
#         return context

#     def dispatch(self, request, *args, **kwargs):
#         membership_check = self.check_membership_or_redirect()
#         if isinstance(membership_check, HttpResponseRedirect):
#             team, user_membership = self.get_team_and_membership()
#             if user_membership:
#                 return super().dispatch(request, *args, **kwargs)
#             return membership_check
#         return super().dispatch(request, *args, **kwargs)


# class TeamDashboardView(LoginRequiredMixin, TeamMembershipMixin, TemplateView):
#     template_name = "team/overview.html"

#     def get_context_data(self, **kwargs):
#         return super().get_context_data(**kwargs)


# class TeamMembersView(LoginRequiredMixin, TeamMembershipMixin, ListView):
#     template_name = "team/members.html"
#     context_object_name = "members"
#     model = TeamMembership

#     def post(self, request, *args, **kwargs):
#         team, user_membership = self.get_team_and_membership()

#         print(f"Processing POST request for team: {team.slug}")

#         if not user_membership:
#             return HttpResponseRedirect(
#                 reverse("team-catalog", kwargs={"team": team.slug})
#             )

#         if request.user.is_superuser or user_membership.role in ["Admin", "Owner"]:
#             action = request.POST.get("action")
#             user_id = request.POST.get("user_id")
#             role = request.POST.get("role")

#             print(f"Action: {action}, User ID: {user_id}")

#             if action == "add":
#                 print(f"Inviting user {user_id} to team {team.slug}")
#                 user_email = request.POST.get("email")

#                 # Check if an invitation already exists
#                 invite, created = TeamInvite.objects.get_or_create(
#                     email=user_email, team=team
#                 )

#                 if not created:
#                     # Update expiration and resend
#                     invite.expires_at = timezone.now() + timezone.timedelta(days=7)
#                     invite.save()
#                 else:
#                     # Set expiration for new invite
#                     invite.expires_at = timezone.now() + timezone.timedelta(days=7)
#                     invite.save()

#                 invitation_link = invite.invite_link()
#                 message = (
#                     f"You have been invited to join the team {team.name}. "
#                     f"Please click the link below to accept the invitation:\n\n{invitation_link}"
#                 )
#                 send_mail(
#                     subject="Team Invitation",
#                     message=message,
#                     from_email="no-reply@microdrama.com",
#                     recipient_list=[user_email],
#                     fail_silently=False,
#                 )

#             elif action == "remove":
#                 membership = get_object_or_404(
#                     TeamMembership, user_id=user_id, team=team
#                 )
#                 if membership.role != "Owner" or request.user.is_superuser:
#                     membership.delete()

#             elif action == "update_role":
#                 membership = get_object_or_404(
#                     TeamMembership, user_id=user_id, team=team
#                 )
#                 if membership.role != "Owner" or request.user.is_superuser:
#                     membership.role = role
#                     membership.save()

#         return HttpResponseRedirect(
#             reverse("team-members", kwargs={"team_slug": team.slug})
#         )

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         team, user_membership = self.get_team_and_membership()
#         context.update({"team": team, "user_membership": user_membership})
#         return context


# class TeamContentView(LoginRequiredMixin, TeamMembershipMixin, ListView):
#     template_name = "team/content.html"
#     context_object_name = "content"
#     model = Series

#     def get_context_data(self, **kwargs):
#         return super().get_context_data(**kwargs)


# class TeamShortLinkView(LoginRequiredMixin, TeamMembershipMixin, TemplateView):
#     template_name = "team/team_shortlink.html"

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         team = self.request.user.teams.first()  # Assuming single team membership
#         series_list = Series.objects.filter(team=team)
#         context.update(
#             {
#                 "series_list": series_list,
#                 "referral_links": ReferralLink.objects.filter(team=team),
#             }
#         )
#         return context

#     def post(self, request, *args, **kwargs):
#         team, user_membership = self.get_team_and_membership()
#         if not user_membership:
#             return HttpResponseRedirect(
#                 reverse("team-catalog", kwargs={"team": team.slug})
#             )

#         episode_id = request.POST.get("episode_id")
#         link_name = request.POST.get("link_name")

#         if episode_id and link_name:
#             episode = get_object_or_404(Episode, id=episode_id)
#             try:
#                 ReferralLink.objects.create(name=link_name, episode=episode, team=team)
#             except IntegrityError:
#                 messages.error(
#                     request,
#                     "A link with this slug already exists. Please try again with a different name.",
#                 )
#                 return HttpResponseRedirect(
#                     reverse("team-shortlinks", kwargs={"team_slug": team.slug})
#                 )

#         return HttpResponseRedirect(
#             reverse("team-shortlinks", kwargs={"team_slug": team.slug})
#         )


# class AcceptInviteView(LoginRequiredMixin, View):
#     def get(self, request, token):
#         invite = get_object_or_404(TeamInvite, token=token)
#         if invite.accepted_at:
#             return render(request, "team/invite_already_accepted.html")

#         # check if the invite is expired
#         if invite.is_expired():
#             return render(request, "team/invite_expired.html")

#         # check if the current user email matches the invite email
#         if request.user.email != invite.email:
#             return render(request, "team/invite_email_mismatch.html")

#         return render(request, "team/accept_invite.html", {"invite": invite})

#     def post(self, request, token):
#         invite = get_object_or_404(TeamInvite, token=token)
#         if invite.accepted_at:
#             return render(request, "team/invite_already_accepted.html")

#         if request.user.email != invite.email:
#             return render(request, "team/invite_email_mismatch.html")

#         if invite.is_expired():
#             return render(request, "team/invite_expired.html")

#         TeamMembership.objects.create(
#             user=request.user, team=invite.team, role=TeamMembership.Role.MEMBER
#         )
#         invite.accepted_at = timezone.now()
#         invite.save()
#         return redirect("team-overview", team_slug=invite.team.slug)
