"""
Referral attribution signal.

When a user logs in, look for the most recent unattributed ReferralClick that
shares the same anonymous_id cookie (last-touch attribution, 30-day window).
If found, stamp it with the user and emit a referral.attributed BigQuery event.
"""

import uuid
from datetime import timedelta

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone

from events.emit import TOPIC_REFERRALS, emit
from events.schemas import ReferralClickEvent

from .models import ReferralClick


@receiver(user_logged_in)
def attribute_referral_click(sender, request, user, **kwargs):
    """
    Last-touch attribution: find the most recent unattributed ReferralClick
    for this anonymous_id within the 30-day attribution window, then mark it.
    """
    raw_anon = request.COOKIES.get(ReferralClick.ANON_COOKIE)
    if not raw_anon:
        return

    try:
        anonymous_id = uuid.UUID(raw_anon)
    except ValueError:
        return

    window_start = timezone.now() - timedelta(days=30)

    click = (
        ReferralClick.objects.filter(
            anonymous_id=anonymous_id,
            user__isnull=True,
            clicked_at__gte=window_start,
        )
        .select_related("referral_link__show")
        .order_by("-clicked_at")
        .first()
    )
    if not click:
        return

    # Determine whether this is a new user (registered after the click).
    is_new_user = user.date_joined >= click.clicked_at

    now = timezone.now()
    ReferralClick.objects.filter(pk=click.pk).update(
        user=user,
        is_new_user=is_new_user,
        attributed_at=now,
    )

    emit(
        TOPIC_REFERRALS,
        ReferralClickEvent(
            event_type="referral.attributed",
            referral_click_id=str(click.pk),
            referral_link_id=str(click.referral_link_id),
            referral_slug=click.referral_link.slug,
            show_id=str(click.referral_link.show.uuid),
            anonymous_id=str(anonymous_id),
            user_id=str(user.pk),
            is_new_user=is_new_user,
            ip_address=click.ip_address or "",
            user_agent=click.user_agent,
        ),
    )
