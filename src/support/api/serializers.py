from django.utils import timezone
from django.utils.timesince import timesince
from rest_framework import serializers

from ..models import (
    HelpArticle,
    HelpCategory,
    HelpFAQ,
    SupportTicket,
    TicketAttachment,
    TicketMessage,
)

# ── Ticket Serializers ────────────────────────────────────────────────────────


class TicketAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketAttachment
        fields = ["id", "filename", "url", "uploaded_at"]


class TicketMessageSerializer(serializers.ModelSerializer):
    ticketId = serializers.IntegerField(source="ticket_id")
    senderId = serializers.CharField(source="sender_id")
    senderName = serializers.SerializerMethodField()
    senderRole = serializers.CharField(source="sender_role")
    attachments = TicketAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = TicketMessage
        fields = [
            "id",
            "ticketId",
            "senderId",
            "senderName",
            "senderRole",
            "message",
            "timestamp",
            "attachments",
        ]

    def get_senderName(self, obj):
        return obj.sender.get_full_name() or obj.sender.username


class SupportTicketSerializer(serializers.ModelSerializer):
    userId = serializers.CharField(source="user_id")
    userName = serializers.SerializerMethodField()
    userEmail = serializers.SerializerMethodField()
    assignedTo = serializers.CharField(source="assigned_to_id", allow_null=True)
    createdAt = serializers.DateTimeField(source="created_at")
    updatedAt = serializers.DateTimeField(source="updated_at")
    messages = TicketMessageSerializer(many=True, read_only=True)

    class Meta:
        model = SupportTicket
        fields = [
            "id",
            "userId",
            "userName",
            "userEmail",
            "subject",
            "category",
            "priority",
            "status",
            "description",
            "assignedTo",
            "resolution",
            "createdAt",
            "updatedAt",
            "messages",
        ]

    def get_userName(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def get_userEmail(self, obj):
        return obj.user.email


# ── Help Center Serializers ───────────────────────────────────────────────────


def _pick_translation(translations, lang):
    """
    Pick the best translation from a prefetched set.
    Returns the entry for `lang` if present, otherwise falls back to 'en'.
    """
    by_code = {t.language.code: t for t in translations}
    return by_code.get(lang) or by_code.get("en")


class HelpCategorySerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="slug")
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    class Meta:
        model = HelpCategory
        fields = ["id", "title", "description", "icon", "color"]

    def get_title(self, obj):
        t = _pick_translation(obj.translations.all(), self.context.get("lang", "en"))
        return t.title if t else ""

    def get_description(self, obj):
        t = _pick_translation(obj.translations.all(), self.context.get("lang", "en"))
        return t.description if t else ""


class HelpArticleSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    readTime = serializers.SerializerMethodField()
    lastUpdated = serializers.SerializerMethodField()

    class Meta:
        model = HelpArticle
        fields = ["id", "title", "description", "category", "readTime", "lastUpdated"]

    def get_title(self, obj):
        t = _pick_translation(obj.translations.all(), self.context.get("lang", "en"))
        return t.title if t else ""

    def get_description(self, obj):
        t = _pick_translation(obj.translations.all(), self.context.get("lang", "en"))
        return t.description if t else ""

    def get_readTime(self, obj):
        return f"{obj.read_time_minutes} min"

    def get_lastUpdated(self, obj):
        # Returns the most significant unit only, e.g. "2 days" or "1 week"
        return timesince(obj.updated_at, timezone.now()).split(",")[0]


class HelpArticleDetailSerializer(HelpArticleSerializer):
    categoryTitle = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()
    author = serializers.CharField()
    authorRole = serializers.CharField(source="author_role")

    class Meta(HelpArticleSerializer.Meta):
        fields = HelpArticleSerializer.Meta.fields + [
            "categoryTitle",
            "content",
            "author",
            "authorRole",
        ]

    def get_categoryTitle(self, obj):
        lang = self.context.get("lang", "en")
        t = _pick_translation(obj.category.translations.all(), lang)
        return t.title if t else obj.category.slug

    def get_content(self, obj):
        t = _pick_translation(obj.translations.all(), self.context.get("lang", "en"))
        return t.content if t else ""


class HelpFAQSerializer(serializers.ModelSerializer):
    question = serializers.SerializerMethodField()
    answer = serializers.SerializerMethodField()
    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)

    class Meta:
        model = HelpFAQ
        fields = ["id", "question", "answer", "category"]

    def get_question(self, obj):
        t = _pick_translation(obj.translations.all(), self.context.get("lang", "en"))
        return t.question if t else ""

    def get_answer(self, obj):
        t = _pick_translation(obj.translations.all(), self.context.get("lang", "en"))
        return t.answer if t else ""
