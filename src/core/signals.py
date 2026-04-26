"""
Auth event signals — emit BigQuery audit events for login, logout, and
login-failure lifecycle transitions.

Password-reset events are emitted directly in the view layer
(core/api/views.py) since there is no corresponding Django signal.
"""

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver

from events.emit import TOPIC_AUDIT, emit
from events.schemas import AuthEvent


def _ip(request) -> str:
    if request is None:
        return ""
    return request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[
        0
    ].strip() or request.META.get("REMOTE_ADDR", "")


def _ua(request) -> str:
    if request is None:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    emit(
        TOPIC_AUDIT,
        AuthEvent(
            event_type="auth.login_success",
            user_id=str(user.pk),
            ip_address=_ip(request),
            user_agent=_ua(request),
        ),
    )


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    emit(
        TOPIC_AUDIT,
        AuthEvent(
            event_type="auth.logout",
            user_id=str(user.pk) if user else None,
            ip_address=_ip(request),
            user_agent=_ua(request),
        ),
    )


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request, **kwargs):
    emit(
        TOPIC_AUDIT,
        AuthEvent(
            event_type="auth.login_failure",
            email=credentials.get("email") or credentials.get("username"),
            ip_address=_ip(request),
            user_agent=_ua(request),
            failure_reason="invalid_credentials",
        ),
    )
