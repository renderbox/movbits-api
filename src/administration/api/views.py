from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from events.emit import TOPIC_AUDIT, emit
from events.schemas import AdminAuditEvent

from .serializers import AdminUserSerializer

User = get_user_model()


def _ip(request) -> str:
    return (
        request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        or request.META.get("REMOTE_ADDR", "")
    )


# ── Dashboard stats ────────────────────────────────────────────────────────────


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_stats(request):
    from shows.models import Episode

    return Response(
        {
            "totalUsers": User.objects.count(),
            "activeUsers": User.objects.filter(is_active=True).count(),
            "totalContent": Episode.objects.filter(active=True).count(),
            # TODO: wire to billing app
            "pendingReviews": 0,
            "revenue": 0,
            "systemHealth": 100,
        }
    )


# ── User management (real) ─────────────────────────────────────────────────────


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_users_list(request):
    qs = User.objects.all().order_by("-date_joined")

    search = request.query_params.get("search", "").strip()
    if search:
        qs = qs.filter(
            Q(email__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(username__icontains=search)
        )

    role = request.query_params.get("role", "").strip()
    if role == "admin":
        qs = qs.filter(Q(is_staff=True) | Q(is_superuser=True))
    elif role in ("viewer", "creator", "moderator"):
        qs = qs.filter(is_staff=False, is_superuser=False)

    status = request.query_params.get("status", "").strip()
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status in ("inactive", "suspended"):
        qs = qs.filter(is_active=False)

    limit = min(int(request.query_params.get("limit", 50)), 200)
    page = max(int(request.query_params.get("page", 1)), 1)
    offset = (page - 1) * limit
    qs = qs[offset : offset + limit]  # noqa: E203

    return Response(AdminUserSerializer(qs, many=True, context={"request": request}).data)


@api_view(["PUT"])
@permission_classes([IsAdminUser])
def admin_user_update_status(request, user_id):
    if not request.user.is_superuser:
        return Response({"detail": "Superuser access required."}, status=403)
    try:
        user = User.objects.get(pk=int(user_id))
    except (User.DoesNotExist, ValueError):
        return Response({"detail": "User not found."}, status=404)

    new_status = (request.data or {}).get("status", "")
    previous_status = "active" if user.is_active else "inactive"
    user.is_active = new_status == "active"
    user.save(update_fields=["is_active"])
    emit(
        TOPIC_AUDIT,
        AdminAuditEvent(
            event_type="admin.user_status_changed",
            actor_user_id=str(request.user.pk),
            target_type="user",
            target_id=str(user.pk),
            previous_value=previous_status,
            new_value=new_status,
            ip_address=_ip(request),
        ),
    )
    return Response(AdminUserSerializer(user, context={"request": request}).data)


@api_view(["PUT"])
@permission_classes([IsAdminUser])
def admin_user_update_role(request, user_id):
    if not request.user.is_superuser:
        return Response({"detail": "Superuser access required."}, status=403)
    try:
        user = User.objects.get(pk=int(user_id))
    except (User.DoesNotExist, ValueError):
        return Response({"detail": "User not found."}, status=404)

    new_role = (request.data or {}).get("role", "")
    previous_role = "admin" if user.is_staff else "member"
    user.is_staff = new_role == "admin"
    user.save(update_fields=["is_staff"])
    emit(
        TOPIC_AUDIT,
        AdminAuditEvent(
            event_type="admin.user_role_changed",
            actor_user_id=str(request.user.pk),
            target_type="user",
            target_id=str(user.pk),
            previous_value=previous_role,
            new_value=new_role,
            ip_address=_ip(request),
        ),
    )
    return Response(AdminUserSerializer(user, context={"request": request}).data)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAdminUser])
def admin_user_detail(request, user_id):
    if not request.user.is_superuser:
        return Response({"detail": "Superuser access required."}, status=403)
    try:
        user = User.objects.get(pk=int(user_id))
    except (User.DoesNotExist, ValueError):
        return Response({"detail": "User not found."}, status=404)

    if request.method == "DELETE":
        emit(
            TOPIC_AUDIT,
            AdminAuditEvent(
                event_type="admin.user_deleted",
                actor_user_id=str(request.user.pk),
                target_type="user",
                target_id=str(user.pk),
                previous_value=user.email,
                ip_address=_ip(request),
            ),
        )
        user.delete()
        return Response({"success": True})

    data = request.data or {}
    update_fields = []
    if "name" in data:
        parts = data["name"].strip().split(" ", 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ""
        update_fields += ["first_name", "last_name"]
    if "email" in data:
        new_email = data["email"].strip()
        if User.objects.filter(email=new_email).exclude(pk=user.pk).exists():
            return Response({"detail": "Email already in use."}, status=400)
        user.email = new_email
        update_fields.append("email")
    if update_fields:
        user.save(update_fields=update_fields)
        emit(
            TOPIC_AUDIT,
            AdminAuditEvent(
                event_type="admin.user_updated",
                actor_user_id=str(request.user.pk),
                target_type="user",
                target_id=str(user.pk),
                notes=f"updated fields: {', '.join(update_fields)}",
                ip_address=_ip(request),
            ),
        )
    return Response(AdminUserSerializer(user, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def admin_user_ban(request, user_id):
    if not request.user.is_superuser:
        return Response({"detail": "Superuser access required."}, status=403)
    try:
        user = User.objects.get(pk=int(user_id))
    except (User.DoesNotExist, ValueError):
        return Response({"detail": "User not found."}, status=404)
    user.is_active = False
    user.save(update_fields=["is_active"])
    emit(
        TOPIC_AUDIT,
        AdminAuditEvent(
            event_type="admin.user_suspended",
            actor_user_id=str(request.user.pk),
            target_type="user",
            target_id=str(user.pk),
            notes=(request.data or {}).get("reason", ""),
            ip_address=_ip(request),
        ),
    )
    return Response(AdminUserSerializer(user, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def admin_user_unban(request, user_id):
    if not request.user.is_superuser:
        return Response({"detail": "Superuser access required."}, status=403)
    try:
        user = User.objects.get(pk=int(user_id))
    except (User.DoesNotExist, ValueError):
        return Response({"detail": "User not found."}, status=404)
    user.is_active = True
    user.save(update_fields=["is_active"])
    emit(
        TOPIC_AUDIT,
        AdminAuditEvent(
            event_type="admin.user_activated",
            actor_user_id=str(request.user.pk),
            target_type="user",
            target_id=str(user.pk),
            ip_address=_ip(request),
        ),
    )
    return Response(AdminUserSerializer(user, context={"request": request}).data)


# ── Stubs — wire to real data in future sprints ────────────────────────────────


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_pending_content(request):
    # TODO: wire to shows app (Episode/Video with pending review status)
    return Response([])


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_content_review_detail(request, review_id):
    # TODO: wire to shows app
    return Response({})


@api_view(["POST"])
@permission_classes([IsAdminUser])
def admin_content_approve(request, content_id):
    # TODO: wire to shows app + emit audit event
    return Response({"success": True})


@api_view(["POST"])
@permission_classes([IsAdminUser])
def admin_content_reject(request, content_id):
    # TODO: wire to shows app + emit audit event
    return Response({"success": True})


@api_view(["POST"])
@permission_classes([IsAdminUser])
def admin_content_flag(request, content_id):
    # TODO: wire to shows app + emit audit event
    return Response({"success": True})


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_content_stats(request):
    # TODO: wire to shows app
    return Response({"total": 0, "published": 0, "draft": 0, "pending": 0, "byType": {}})


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_transactions_list(request):
    # TODO: wire to billing app (Invoice/WalletTransaction)
    return Response([])


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_transaction_detail(request, transaction_id):
    # TODO: wire to billing app
    return Response({})


@api_view(["POST"])
@permission_classes([IsAdminUser])
def admin_transaction_refund(request, transaction_id):
    # TODO: wire to Stripe refund API via billing app
    return Response({"success": True})


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_system_health(request):
    # TODO: ping DB and Redis; surface real status
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_revenue_stats(request):
    # TODO: wire to billing app / BigQuery
    return Response({"total": 0, "byType": {}, "trend": []})


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_user_growth_stats(request):
    # TODO: wire to analytics / BigQuery
    return Response({"total": 0, "new": 0, "active": 0, "trend": []})


@api_view(["POST"])
@permission_classes([IsAdminUser])
def admin_send_announcement(request):
    # TODO: wire to email/push notification service
    return Response({"success": True})


@api_view(["GET", "PUT"])
@permission_classes([IsAdminUser])
def admin_platform_settings(request):
    # TODO: persist settings; maintenance flag lives in MAINTENANCE_MODE env var
    return Response({"siteName": "MovBits", "maintenance": False})


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_export_report(request, report_type):
    # TODO: wire to BigQuery export
    return Response({"downloadUrl": None})
