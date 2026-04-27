from django.http import JsonResponse


class SuperuserMFARequiredMiddleware:
    """
    Blocks superuser API access until they have configured TOTP.
    Exempt paths: auth endpoints (so they can log in), the 2FA setup
    endpoint itself, and the Django admin (handled separately by allauth).
    """

    _EXEMPT = (
        "/api/auth/",
        "/api/v1/user/2fa/",
        "/admin/",
        "/r/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and request.user.is_superuser
            and request.path.startswith("/api/")
            and not any(request.path.startswith(p) for p in self._EXEMPT)
        ):
            from allauth.mfa.models import Authenticator

            has_totp = Authenticator.objects.filter(
                user=request.user,
                type=Authenticator.Type.TOTP,
            ).exists()
            if not has_totp:
                return JsonResponse(
                    {
                        "detail": (
                            "Two-factor authentication is required for "
                            "admin accounts. Please set up TOTP."
                        ),
                        "code": "mfa_setup_required",
                    },
                    status=403,
                )
        return self.get_response(request)
