import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models

# import survey


class InterestedUser(models.Model):
    email = models.EmailField()
    site = models.ForeignKey(
        "sites.Site", on_delete=models.CASCADE, related_name="interested_users"
    )
    added_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="interested_signups",
    )  # this should be matched if they later register

    class Meta:
        unique_together = ("email", "site")

    def __str__(self):
        return f"{self.email} @ {self.site.domain}"


class Survey(models.Model):
    """
    A survey model is a series of questions that a user is asked to answer.
    The user's answers are recorded in a matching SurveyResult model record.
    """

    class TypeChoices(models.IntegerChoices):
        PRE_PREVIEW = 1, "Pre-Preview"
        POST_PREVIEW = 2, "Post-Preview"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(max_length=255)
    survey_type = models.IntegerField(
        choices=TypeChoices.choices, default=TypeChoices.PRE_PREVIEW
    )
    questions = models.JSONField(help_text="List of survey questions in JSON format")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)


class SurveyResult(models.Model):
    # The list of survey questions can vary so the responses will be put into a JSON field.
    email = models.EmailField()  # Incase the user is not registered
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    responses = models.JSONField()
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="results")
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email

    # On save, if email matches a registered user, link to that user
    def save(self, *args, **kwargs):
        if not self.user:
            try:
                self.user = get_user_model().objects.get(email=self.email)
            except get_user_model().DoesNotExist:
                pass
        super().save(*args, **kwargs)
