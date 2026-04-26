from django.conf import settings
from django.db import models

# ── Choices ───────────────────────────────────────────────────────────────────


class TicketCategory(models.TextChoices):
    GENERAL = "general", "General"
    TECHNICAL = "technical", "Technical"
    BILLING = "billing", "Billing"
    CONTENT = "content", "Content"
    ACCOUNT = "account", "Account"


class TicketPriority(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class TicketStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_PROGRESS = "in-progress", "In Progress"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"


class SenderRole(models.TextChoices):
    USER = "user", "User"
    SUPPORT = "support", "Support"
    ADMIN = "admin", "Admin"


# ── Support Tickets ───────────────────────────────────────────────────────────


class SupportTicket(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_tickets",
    )
    subject = models.CharField(max_length=255)
    category = models.CharField(
        max_length=50,
        choices=TicketCategory.choices,
        default=TicketCategory.GENERAL,
    )
    priority = models.CharField(
        max_length=20,
        choices=TicketPriority.choices,
        default=TicketPriority.MEDIUM,
    )
    status = models.CharField(
        max_length=20,
        choices=TicketStatus.choices,
        default=TicketStatus.OPEN,
    )
    description = models.TextField()
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_support_tickets",
    )
    resolution = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.status}] {self.subject} (#{self.pk})"


class TicketMessage(models.Model):
    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ticket_messages",
    )
    sender_role = models.CharField(
        max_length=20,
        choices=SenderRole.choices,
        default=SenderRole.USER,
    )
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"Message on ticket #{self.ticket_id} by {self.sender}"


class TicketAttachment(models.Model):
    message = models.ForeignKey(
        TicketMessage,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    filename = models.CharField(max_length=255)
    url = models.URLField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.filename


# ── Help Center ───────────────────────────────────────────────────────────────


class HelpCategory(models.Model):
    slug = models.SlugField(unique=True)
    icon = models.CharField(
        max_length=50, help_text="Lucide icon identifier, e.g. 'book-open'"
    )
    color = models.CharField(
        max_length=20, help_text="Tailwind colour name, e.g. 'blue'"
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order"]
        verbose_name_plural = "help categories"

    def __str__(self):
        return self.slug


class HelpCategoryTranslation(models.Model):
    category = models.ForeignKey(
        HelpCategory,
        on_delete=models.CASCADE,
        related_name="translations",
    )
    language = models.ForeignKey(
        "localization.Language",
        on_delete=models.CASCADE,
        related_name="+",
    )
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=500)

    class Meta:
        unique_together = ("category", "language")

    def __str__(self):
        return f"{self.category.slug} [{self.language.code}]"


class HelpArticle(models.Model):
    category = models.ForeignKey(
        HelpCategory,
        on_delete=models.CASCADE,
        related_name="articles",
    )
    slug = models.SlugField(unique=True)
    read_time_minutes = models.PositiveIntegerField(
        help_text="Estimated read time in minutes"
    )
    author = models.CharField(max_length=200, blank=True)
    author_role = models.CharField(max_length=200, blank=True)
    is_popular = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_popular", "category", "id"]

    def __str__(self):
        return self.slug


class HelpArticleTranslation(models.Model):
    article = models.ForeignKey(
        HelpArticle,
        on_delete=models.CASCADE,
        related_name="translations",
    )
    language = models.ForeignKey(
        "localization.Language",
        on_delete=models.CASCADE,
        related_name="+",
    )
    title = models.CharField(max_length=300)
    description = models.TextField()
    content = models.TextField(
        blank=True, help_text="Markdown body for the full article"
    )

    class Meta:
        unique_together = ("article", "language")

    def __str__(self):
        return f"{self.article.slug} [{self.language.code}]"


class HelpFAQ(models.Model):
    category = models.ForeignKey(
        HelpCategory,
        on_delete=models.CASCADE,
        related_name="faqs",
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "order"]
        verbose_name = "help FAQ"

    def __str__(self):
        return f"FAQ #{self.pk} ({self.category.slug})"


class HelpFAQTranslation(models.Model):
    faq = models.ForeignKey(
        HelpFAQ,
        on_delete=models.CASCADE,
        related_name="translations",
    )
    language = models.ForeignKey(
        "localization.Language",
        on_delete=models.CASCADE,
        related_name="+",
    )
    question = models.CharField(max_length=500)
    answer = models.TextField()

    class Meta:
        unique_together = ("faq", "language")

    def __str__(self):
        return f"FAQ #{self.faq_id} [{self.language.code}]"
