from allauth.mfa.adapter import get_adapter as get_mfa_adapter
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import (
    TOTP,
    generate_totp_secret,
    validate_totp_code,
)
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

_PENDING_SECRET_KEY = "mfa.totp.pending_secret"


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def enable_totp(request):
    """
    Two-phase TOTP activation.

    Phase 1 — POST with no body: generates a secret and returns the
    otpauth:// URI for the authenticator app to scan.

    Phase 2 — POST with {"code": "<6-digit code>"}: verifies the code
    against the pending secret and activates TOTP on the account.
    """
    code = (request.data or {}).get("code", "").strip()

    if not code:
        secret = generate_totp_secret()
        request.session[_PENDING_SECRET_KEY] = secret
        adapter = get_mfa_adapter()
        totp_url = adapter.build_totp_url(request.user, secret)
        return Response({"secret": secret, "totp_url": totp_url})

    secret = request.session.get(_PENDING_SECRET_KEY)
    if not secret:
        return Response(
            {"detail": "No pending TOTP setup. POST without a code first."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not validate_totp_code(secret, code):
        return Response(
            {"detail": "Invalid code."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    Authenticator.objects.filter(
        user=request.user, type=Authenticator.Type.TOTP
    ).delete()
    TOTP.activate(request.user, secret)
    request.session.pop(_PENDING_SECRET_KEY, None)

    return Response({"detail": "Two-factor authentication enabled."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def disable_totp(request):
    """
    Deactivates TOTP for the authenticated user.
    Requires the current TOTP code as confirmation.
    Superusers cannot disable their last TOTP authenticator.
    """
    code = (request.data or {}).get("code", "").strip()
    if not code:
        return Response(
            {"detail": "code is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        authenticator = Authenticator.objects.get(
            user=request.user, type=Authenticator.Type.TOTP
        )
    except Authenticator.DoesNotExist:
        return Response(
            {"detail": "Two-factor authentication is not enabled."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    adapter = get_mfa_adapter()
    if not adapter.can_delete_authenticator(authenticator):
        return Response(
            {
                "detail": (
                    "Two-factor authentication cannot be disabled "
                    "for admin accounts."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    totp = TOTP(authenticator)
    if not totp.validate_code(code):
        return Response(
            {"detail": "Invalid code."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    authenticator.delete()
    return Response({"detail": "Two-factor authentication disabled."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def totp_status(request):
    """Returns whether TOTP is configured for the authenticated user."""
    enabled = Authenticator.objects.filter(
        user=request.user, type=Authenticator.Type.TOTP
    ).exists()
    return Response({"totp_enabled": enabled})
