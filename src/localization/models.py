from django.db import models


class Language(models.Model):
    code = models.CharField(
        max_length=10,
        unique=True,
        help_text="BCP-47 language code, e.g. 'en', 'es', 'es-MX'.",
    )
    name = models.CharField(
        max_length=100,
        help_text="Native name shown to the user, e.g. 'Español'.",
    )
    display_name = models.CharField(
        max_length=100,
        help_text="English name for internal reference, e.g. 'Spanish'.",
    )
    flag = models.CharField(
        max_length=10,
        blank=True,
        help_text="Flag emoji, e.g. '🇪🇸'.",
    )
    is_rtl = models.BooleanField(
        default=False,
        help_text="Right-to-left script (Arabic, Hebrew, etc.).",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Only active languages are returned to clients.",
    )

    class Meta:
        ordering = ["display_name"]

    def __str__(self):
        return f"{self.display_name} ({self.code})"


class Translation(models.Model):
    language = models.ForeignKey(
        Language,
        on_delete=models.CASCADE,
        related_name="translations",
    )
    key = models.CharField(
        max_length=255,
        help_text="Dot-separated key, e.g. 'login.title'.",
    )
    value = models.TextField()

    class Meta:
        unique_together = ("language", "key")
        ordering = ["key"]

    def __str__(self):
        return f"{self.language.code}:{self.key}"
