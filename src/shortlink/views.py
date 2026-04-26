import uuid

from django.conf import settings
from django.db import models
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

from events.emit import TOPIC_REFERRALS, emit
from events.schemas import ReferralClickEvent

from .models import ReferralClick, ReferralLink


def referral_view(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Non-API referral redirect view — used when following a bare /r/<slug> URL.

    Records a ReferralClick, sets the mvb_anon_id cookie, and redirects the
    visitor to the SPA show page so the frontend can handle the deep-link.
    """
    referral = (
        ReferralLink.objects.filter(slug=slug, deleted=False)
        .select_related("show")
        .first()
    )
    if not referral:
        return redirect(getattr(settings, "SPA_BASE_URL", "/"))

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

    # Store in session so the login signal can attribute this click.
    request.session["referral_click_id"] = click.pk
    request.session["referral_show_id"] = referral.show_id

    # Keep legacy click_count in sync.
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

    spa_base = getattr(settings, "SPA_BASE_URL", "").rstrip("/")
    response = redirect(f"{spa_base}/show/{referral.show.slug}")
    response.set_cookie(
        ReferralClick.ANON_COOKIE,
        str(anonymous_id),
        max_age=ReferralClick.ANON_COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
    )
    return response
