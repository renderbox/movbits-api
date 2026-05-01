import uuid

from django.conf import settings
from django.contrib.sites.models import Site
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.text import slugify


def get_rando_str():
    return get_random_string(64)


class Team(models.Model):

    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=255, unique=True)
    verified = models.BooleanField(default=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="TeamMembership",
        related_name="teams",
    )
    sites = models.ManyToManyField(Site, related_name="teams")
    avatar = models.ImageField(
        upload_to="team/", null=True, blank=True
    )  # TODO: store in team/<team_id>/avatar.<ext>, accept jpg/png/gif only,
    #   resize to 100x100 and 500x500, keep original.

    class Meta:
        permissions = [
            ("member", "Team Member"),
            ("admin", "Team Admin"),
            ("owner", "Team Owner"),
        ]

    def __str__(self):
        return self.name

    # update the slug on every save
    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class TeamMembership(models.Model):
    class Role(models.IntegerChoices):
        OWNER = 1, "Owner"
        ADMIN = 2, "Admin"
        EDITOR = 3, "Editor"
        VIEWER = 4, "Viewer"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    role = models.IntegerField(choices=Role.choices, default=Role.VIEWER)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.team} ({self.get_role_display()})"


class TeamInvite(models.Model):
    email = models.EmailField(max_length=255)
    team = models.ForeignKey("Team", on_delete=models.CASCADE, related_name="invites")
    token = models.CharField(max_length=64, unique=True, default=get_rando_str)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def accept(self, user):
        if user.email != self.email:
            raise ValueError("Email mismatch. Cannot accept invite.")
        TeamMembership.objects.create(
            user=user, team=self.team, role=TeamMembership.Role.VIEWER
        )
        self.accepted_at = timezone.now()
        self.save()

    def invite_link(self):
        from django.contrib.sites.models import Site
        from django.urls import reverse

        current_site = Site.objects.get_current()
        return f"https://{current_site.domain}{reverse('accept-invite', kwargs={'token': self.token})}"

    def is_expired(self):
        return self.expires_at and timezone.now() > self.expires_at

    def __str__(self):
        return f"Invite for {self.email} to join {self.team.name}"
