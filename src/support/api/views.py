import uuid

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import (
    Avg,
    Count,
    DurationField,
    ExpressionWrapper,
    F,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
)
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    HelpArticle,
    HelpArticleTranslation,
    HelpCategory,
    HelpCategoryTranslation,
    HelpFAQ,
    HelpFAQTranslation,
    SenderRole,
    SupportTicket,
    TicketAttachment,
    TicketMessage,
    TicketStatus,
)
from .serializers import (
    HelpArticleDetailSerializer,
    HelpArticleSerializer,
    HelpCategorySerializer,
    HelpFAQSerializer,
    SupportTicketSerializer,
    TicketMessageSerializer,
)

User = get_user_model()

_ATTACHMENT_BASE_URL = "https://example.com/uploads"


def _require_auth(request):
    if not request.user.is_authenticated:
        return Response(
            {"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED
        )
    return None


def _require_staff(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)
    return None


def _get_ticket_or_404(ticket_id, user):
    """Return (ticket, None) if accessible, or (None, error_response)."""
    qs = (
        SupportTicket.objects.all()
        if user.is_staff
        else SupportTicket.objects.filter(user=user)
    )
    try:
        return qs.get(pk=ticket_id), None
    except SupportTicket.DoesNotExist:
        return None, Response(
            {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND
        )


def _ticket_qs(base_qs):
    return base_qs.select_related("user", "assigned_to").prefetch_related(
        Prefetch(
            "messages",
            queryset=TicketMessage.objects.select_related("sender").prefetch_related(
                "attachments"
            ),
        )
    )


# ── Tickets list / create ─────────────────────────────────────────────────────


@api_view(["GET", "POST"])
def tickets_list(request):
    if err := _require_auth(request):
        return err

    if request.method == "GET":
        qs = _ticket_qs(SupportTicket.objects.filter(user=request.user))
        return Response(SupportTicketSerializer(qs, many=True).data)

    payload = request.data or {}
    subject = payload.get("subject", "").strip()
    if not subject:
        return Response(
            {"detail": "subject is required."}, status=status.HTTP_400_BAD_REQUEST
        )

    with transaction.atomic():
        ticket = SupportTicket.objects.create(
            user=request.user,
            subject=subject,
            description=payload.get("description", ""),
            category=payload.get("category", "general"),
            priority=payload.get("priority", "medium"),
        )
        TicketMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            sender_role=SenderRole.USER,
            message=payload.get("description") or subject,
        )

    ticket = _ticket_qs(SupportTicket.objects.filter(pk=ticket.pk)).get()
    return Response(
        SupportTicketSerializer(ticket).data, status=status.HTTP_201_CREATED
    )


# ── Admin list ────────────────────────────────────────────────────────────────


@api_view(["GET"])
def admin_tickets_list(request):
    if err := _require_staff(request):
        return err

    qs = _ticket_qs(SupportTicket.objects.all())
    params = request.query_params

    if s := params.get("status"):
        qs = qs.filter(status=s)
    if p := params.get("priority"):
        qs = qs.filter(priority=p)
    if c := params.get("category"):
        qs = qs.filter(category=c)
    if a := params.get("assignedTo"):
        qs = qs.filter(assigned_to_id=a)
    if q := params.get("search"):
        qs = qs.filter(
            Q(subject__icontains=q)
            | Q(description__icontains=q)
            | Q(user__username__icontains=q)
        )

    try:
        limit = int(params.get("limit", 0)) or None
        page = max(int(params.get("page", 1)), 1)
    except (ValueError, TypeError):
        limit = None
        page = 1

    if limit:
        start = (page - 1) * limit
        qs = qs[start : start + limit]  # noqa: E203

    return Response(SupportTicketSerializer(qs, many=True).data)


# ── Ticket detail / delete ────────────────────────────────────────────────────


@api_view(["GET", "DELETE"])
def ticket_detail(request, ticket_id: str):
    if err := _require_auth(request):
        return err

    ticket, err = _get_ticket_or_404(ticket_id, request.user)
    if err:
        return err
    assert ticket is not None

    if request.method == "GET":
        ticket = _ticket_qs(SupportTicket.objects.filter(pk=ticket.pk)).get()
        return Response(SupportTicketSerializer(ticket).data)

    ticket.delete()
    return Response({"success": True})


# ── Messages ──────────────────────────────────────────────────────────────────


@api_view(["GET", "POST"])
def ticket_messages(request, ticket_id: str):
    if err := _require_auth(request):
        return err

    ticket, err = _get_ticket_or_404(ticket_id, request.user)
    if err:
        return err
    assert ticket is not None

    if request.method == "GET":
        msgs = (
            TicketMessage.objects.filter(ticket=ticket)
            .select_related("sender")
            .prefetch_related("attachments")
        )
        return Response(TicketMessageSerializer(msgs, many=True).data)

    payload = request.data or {}
    message_text = payload.get("message", "").strip()
    if not message_text:
        return Response(
            {"detail": "message is required."}, status=status.HTTP_400_BAD_REQUEST
        )

    role = SenderRole.SUPPORT if request.user.is_staff else SenderRole.USER
    with transaction.atomic():
        msg = TicketMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            sender_role=role,
            message=message_text,
        )
        for att in payload.get("attachments") or []:
            if isinstance(att, dict):
                TicketAttachment.objects.create(
                    message=msg,
                    filename=att.get("filename") or att.get("url", "").split("/")[-1],
                    url=att.get("url", ""),
                )
            elif isinstance(att, str) and att:
                TicketAttachment.objects.create(
                    message=msg,
                    filename=att.split("/")[-1],
                    url=att,
                )
        ticket.save()  # touch updated_at

    msg = (
        TicketMessage.objects.select_related("sender")
        .prefetch_related("attachments")
        .get(pk=msg.pk)
    )
    return Response(TicketMessageSerializer(msg).data, status=status.HTTP_201_CREATED)


def ticket_add_message(request, ticket_id: str):
    return ticket_messages(request, ticket_id)


def ticket_get_messages(request, ticket_id: str):
    return ticket_messages(request, ticket_id)


# ── Status / Priority / Assign / Close / Reopen ───────────────────────────────


def _get_ticket_staff_only(ticket_id, request):
    if err := _require_staff(request):
        return None, err
    try:
        return SupportTicket.objects.get(pk=ticket_id), None
    except SupportTicket.DoesNotExist:
        return None, Response(
            {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND
        )


@api_view(["PUT"])
def ticket_update_status(request, ticket_id: str):
    ticket, err = _get_ticket_staff_only(ticket_id, request)
    if err:
        return err
    assert ticket is not None
    ticket.status = request.data.get("status", ticket.status)
    ticket.save()
    return Response(
        SupportTicketSerializer(
            _ticket_qs(SupportTicket.objects.filter(pk=ticket.pk)).get()
        ).data
    )


@api_view(["PUT"])
def ticket_update_priority(request, ticket_id: str):
    ticket, err = _get_ticket_staff_only(ticket_id, request)
    if err:
        return err
    assert ticket is not None
    ticket.priority = request.data.get("priority", ticket.priority)
    ticket.save()
    return Response(
        SupportTicketSerializer(
            _ticket_qs(SupportTicket.objects.filter(pk=ticket.pk)).get()
        ).data
    )


@api_view(["PUT"])
def ticket_assign(request, ticket_id: str):
    ticket, err = _get_ticket_staff_only(ticket_id, request)
    if err:
        return err
    assert ticket is not None
    agent_id = request.data.get("agentId")
    if agent_id:
        try:
            ticket.assigned_to = User.objects.get(pk=agent_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "Agent not found."}, status=status.HTTP_400_BAD_REQUEST
            )
    else:
        ticket.assigned_to = None
    ticket.save()
    return Response(
        SupportTicketSerializer(
            _ticket_qs(SupportTicket.objects.filter(pk=ticket.pk)).get()
        ).data
    )


@api_view(["POST"])
def ticket_close(request, ticket_id: str):
    if err := _require_auth(request):
        return err
    ticket, err = _get_ticket_or_404(ticket_id, request.user)
    if err:
        return err
    assert ticket is not None
    ticket.status = TicketStatus.CLOSED
    ticket.resolution = request.data.get("resolution", "")
    ticket.save()
    return Response(
        SupportTicketSerializer(
            _ticket_qs(SupportTicket.objects.filter(pk=ticket.pk)).get()
        ).data
    )


@api_view(["POST"])
def ticket_reopen(request, ticket_id: str):
    if err := _require_auth(request):
        return err
    ticket, err = _get_ticket_or_404(ticket_id, request.user)
    if err:
        return err
    assert ticket is not None
    ticket.status = TicketStatus.IN_PROGRESS
    ticket.save()
    return Response(
        SupportTicketSerializer(
            _ticket_qs(SupportTicket.objects.filter(pk=ticket.pk)).get()
        ).data
    )


# ── Attachment upload ─────────────────────────────────────────────────────────


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
def ticket_upload_attachment(request, ticket_id: str):
    if err := _require_auth(request):
        return err
    file_obj = request.FILES.get("file") or request.FILES.get("attachment")
    if not file_obj:
        return Response(
            {"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST
        )
    filename = file_obj.name
    url = f"{_ATTACHMENT_BASE_URL}/{uuid.uuid4()}/{filename}"
    return Response({"url": url, "filename": filename})


# ── Stats / Search / Mark read / Unread count ─────────────────────────────────


@api_view(["GET"])
def tickets_stats(request):
    if err := _require_staff(request):
        return err

    counts = SupportTicket.objects.aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status=TicketStatus.OPEN)),
        in_progress=Count("id", filter=Q(status=TicketStatus.IN_PROGRESS)),
        resolved=Count("id", filter=Q(status=TicketStatus.RESOLVED)),
        closed=Count("id", filter=Q(status=TicketStatus.CLOSED)),
    )

    avg_duration = (
        SupportTicket.objects.filter(
            status__in=[TicketStatus.RESOLVED, TicketStatus.CLOSED]
        )
        .annotate(
            duration=ExpressionWrapper(
                F("updated_at") - F("created_at"), output_field=DurationField()
            )
        )
        .aggregate(avg=Avg("duration"))["avg"]
    )
    avg_resolve_hours = int(avg_duration.total_seconds() / 3600) if avg_duration else 0

    return Response(
        {
            "total": counts["total"],
            "open": counts["open"],
            "inProgress": counts["in_progress"],
            "resolved": counts["resolved"],
            "closed": counts["closed"],
            "averageResponseTime": 0,
            "averageResolutionTime": avg_resolve_hours,
        }
    )


@api_view(["GET"])
def tickets_search(request):
    if err := _require_auth(request):
        return err

    q = request.query_params.get("q", "").strip()
    if not q:
        return Response([])

    base = (
        SupportTicket.objects.all()
        if request.user.is_staff
        else SupportTicket.objects.filter(user=request.user)
    )
    qs = _ticket_qs(base.filter(Q(subject__icontains=q) | Q(description__icontains=q)))
    return Response(SupportTicketSerializer(qs, many=True).data)


@api_view(["POST"])
def ticket_mark_read(request, ticket_id: str):
    if err := _require_auth(request):
        return err
    _, err = _get_ticket_or_404(ticket_id, request.user)
    if err:
        return Response({"success": False}, status=status.HTTP_404_NOT_FOUND)
    return Response({"success": True})


@api_view(["GET"])
def tickets_unread_count(request):
    if err := _require_auth(request):
        return err

    latest_role = (
        TicketMessage.objects.filter(ticket=OuterRef("pk"))
        .order_by("-timestamp")
        .values("sender_role")[:1]
    )
    count = (
        SupportTicket.objects.filter(user=request.user)
        .annotate(last_role=Subquery(latest_role))
        .filter(last_role__in=[SenderRole.SUPPORT, SenderRole.ADMIN])
        .count()
    )
    return Response({"count": count})


# ── Help Center ───────────────────────────────────────────────────────────────


def _lang_param(request):
    return request.query_params.get("lang", "en").lower()


def _translation_prefetch(model, lang):
    lang_codes = list({lang, "en"})
    return Prefetch(
        "translations",
        queryset=model.objects.filter(language__code__in=lang_codes).select_related(
            "language"
        ),
    )


class HelpCategoriesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        lang = _lang_param(request)
        categories = HelpCategory.objects.filter(is_active=True).prefetch_related(
            _translation_prefetch(HelpCategoryTranslation, lang)
        )
        serializer = HelpCategorySerializer(
            categories, many=True, context={"lang": lang}
        )
        return Response({"categories": serializer.data, "language": lang})


class HelpArticlesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        lang = _lang_param(request)
        qs = (
            HelpArticle.objects.filter(is_active=True)
            .prefetch_related(_translation_prefetch(HelpArticleTranslation, lang))
            .select_related("category")
        )
        if c := request.query_params.get("category"):
            qs = qs.filter(category__slug=c)
        if request.query_params.get("popular", "").lower() == "true":
            qs = qs.filter(is_popular=True)
        serializer = HelpArticleSerializer(qs, many=True, context={"lang": lang})
        return Response({"articles": serializer.data, "language": lang})


class HelpFAQsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        lang = _lang_param(request)
        qs = (
            HelpFAQ.objects.filter(is_active=True)
            .prefetch_related(_translation_prefetch(HelpFAQTranslation, lang))
            .select_related("category")
        )
        if c := request.query_params.get("category"):
            qs = qs.filter(category__slug=c)
        serializer = HelpFAQSerializer(qs, many=True, context={"lang": lang})
        return Response({"faqs": serializer.data, "language": lang})


class HelpArticleDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, article_id: int):
        lang = _lang_param(request)
        lang_codes = list({lang, "en"})
        try:
            article = (
                HelpArticle.objects.filter(is_active=True)
                .prefetch_related(
                    _translation_prefetch(HelpArticleTranslation, lang),
                    Prefetch(
                        "category__translations",
                        queryset=HelpCategoryTranslation.objects.filter(
                            language__code__in=lang_codes
                        ).select_related("language"),
                    ),
                )
                .select_related("category")
                .get(pk=article_id)
            )
        except HelpArticle.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = HelpArticleDetailSerializer(article, context={"lang": lang})
        return Response({"article": serializer.data, "language": lang})
