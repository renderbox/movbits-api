import random
import string
import uuid

from django.db import models
from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from events.emit import TOPIC_REFERRALS, emit
from events.schemas import ReferralClickEvent
from shortlink.api.serializers import ReferralLinkSerializer
from shortlink.models import ReferralClick, ReferralLink
from shows.models import Show


def _parse_uuid(value):
    try:
        return __import__("uuid").UUID(str(value))
    except (ValueError, AttributeError):
        return None


def _get_show_or_404(show_id):
    parsed_uuid = _parse_uuid(show_id)
    if parsed_uuid:
        show = Show.objects.filter(
            models.Q(slug=show_id) | models.Q(uuid=parsed_uuid)
        ).first()
    else:
        show = Show.objects.filter(slug=show_id).first()
    if not show:
        return None, Response(
            {"detail": "Show not found."}, status=status.HTTP_404_NOT_FOUND
        )
    return show, None


def _generate_code(length=8):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


# ── Creator CRUD ──────────────────────────────────────────────────────────────


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def referral_links(request):
    """List or create referral links for a show."""
    show_slug = request.query_params.get("show") or request.data.get("show")
    if not show_slug:
        return Response(
            {"detail": "show parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    show, err = _get_show_or_404(show_slug)
    if err:
        return err

    if request.method == "GET":
        links = ReferralLink.objects.filter(show=show, deleted=False).order_by("-id")
        serializer = ReferralLinkSerializer(
            links, many=True, context={"request": request}
        )
        return Response(serializer.data)

    # POST — create
    serializer = ReferralLinkSerializer(data=request.data, context={"request": request})
    if serializer.is_valid():
        serializer.save(show=show)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def referral_link_detail(request, slug):
    """Update or soft-delete a referral link."""
    link = ReferralLink.objects.filter(slug=slug, deleted=False).first()
    if not link:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "PATCH":
        serializer = ReferralLinkSerializer(
            link, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # DELETE — soft delete
    link.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def batch_generate(request):
    """Batch-generate unique referral codes for a show."""
    show_slug = request.data.get("show")
    if not show_slug:
        return Response(
            {"detail": "show is required."}, status=status.HTTP_400_BAD_REQUEST
        )

    show, err = _get_show_or_404(show_slug)
    if err:
        return err

    title = request.data.get("title", "Batch Link")
    description = request.data.get("description", "")
    mode = request.data.get("mode", "count")  # 'count' | 'emails'

    if mode == "emails":
        raw = request.data.get("emails", "")
        emails = (
            [e.strip() for e in raw.splitlines() if e.strip()]
            if isinstance(raw, str)
            else raw
        )
    else:
        try:
            count = max(1, min(1000, int(request.data.get("count", 10))))
        except (TypeError, ValueError):
            return Response(
                {"detail": "count must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        emails = [None] * count

    generated = []
    for email in emails:
        code = _generate_code()
        base_slug = slugify(f"{title}-{code}")
        # Ensure uniqueness
        slug = base_slug
        suffix = 0
        while ReferralLink.objects.filter(slug=slug).exists():
            suffix += 1
            slug = f"{base_slug}-{suffix}"

        link = ReferralLink.objects.create(
            show=show,
            slug=slug,
            name=f"{title} — {code}",
            description=description,
            link_type="unique",
            assigned_email=email or "",
        )
        generated.append(
            {
                "code": code,
                "url": ReferralLinkSerializer(
                    link, context={"request": request}
                ).get_url(link),
                "email": email or "",
            }
        )

    return Response(
        {"generated": generated, "count": len(generated)},
        status=status.HTTP_201_CREATED,
    )


# ── Viewer-facing lookup (existing) ──────────────────────────────────────────


@api_view(["GET"])
def referral_lookup(request, slug):
    """
    Resolve a referral slug, record a ReferralClick, and return the show slug
    so the SPA can navigate to the referred content.

    Sets (or reads) the mvb_anon_id cookie so the click can be attributed to
    a user if they log in within the 90-day cookie window.
    """
    referral = (
        ReferralLink.objects.filter(slug=slug, deleted=False)
        .select_related("show")
        .first()
    )
    if not referral:
        return Response(
            {"detail": "Referral not found."}, status=status.HTTP_404_NOT_FOUND
        )

    # Read or generate the anonymous identity cookie.
    raw_anon = request.COOKIES.get(ReferralClick.ANON_COOKIE)
    try:
        anonymous_id = uuid.UUID(raw_anon) if raw_anon else uuid.uuid4()
    except ValueError:
        anonymous_id = uuid.uuid4()

    ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[
        0
    ].strip() or request.META.get("REMOTE_ADDR", "")

    click = ReferralClick.objects.create(
        referral_link=referral,
        anonymous_id=anonymous_id,
        session_key=request.session.session_key or "",
        ip_address=ip or None,
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    # Store the click ID in the session so the login signal can find it.
    request.session["referral_click_id"] = click.pk
    request.session["referral_show_id"] = referral.show_id

    # Keep the legacy click_count in sync for any existing dashboards.
    ReferralLink.objects.filter(pk=referral.pk).update(
        click_count=models.F("click_count") + 1
    )

    emit(
        TOPIC_REFERRALS,
        ReferralClickEvent(
            event_type="referral.clicked",
            referral_click_id=str(click.pk),
            referral_link_id=str(referral.pk),
            referral_slug=referral.slug,
            show_id=str(referral.show.uuid),
            anonymous_id=str(anonymous_id),
            user_id=str(request.user.pk) if request.user.is_authenticated else None,
            ip_address=ip,
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        ),
    )

    response = Response(
        {
            "id": referral.id,
            "slug": referral.slug,
            "showSlug": referral.show.slug,
        }
    )
    response.set_cookie(
        ReferralClick.ANON_COOKIE,
        str(anonymous_id),
        max_age=ReferralClick.ANON_COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
    )
    return response
