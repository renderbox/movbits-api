from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from ..models import Campaign, SiteInvitation
from .serializers import (
    BulkInviteSerializer,
    CampaignSerializer,
    SendInvitationSerializer,
    SiteInvitationSerializer,
)


@api_view(["GET"])
@permission_classes([AllowAny])
def verify_invite(request):
    """
    Public endpoint. SPA calls this when ?invite=<key> is detected in the URL.
    Returns invite details if the key is valid, so the signup form can be pre-filled
    and the preview gate can be bypassed.
    """
    key = request.query_params.get("key", "").strip()
    if not key:
        return Response(
            {"valid": False, "detail": "Key is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        invitation = SiteInvitation.objects.get(key=key)
    except SiteInvitation.DoesNotExist:
        return Response({"valid": False, "detail": "Invalid invitation."})

    if invitation.accepted:
        return Response({"valid": False, "detail": "Invitation already used."})

    if invitation.sent and invitation.key_expired():
        return Response({"valid": False, "detail": "Invitation has expired."})

    return Response({"valid": True, "email": invitation.email, "name": invitation.name})


@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def invitation_list(request):
    """List all invitations or send a single invitation."""
    if request.method == "GET":
        invitations = SiteInvitation.objects.select_related(
            "campaign", "inviter"
        ).order_by("-created")
        return Response(SiteInvitationSerializer(invitations, many=True).data)

    serializer = SendInvitationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    # Block duplicate active invitations for the same email
    active_exists = SiteInvitation.objects.filter(
        email=data["email"],
        accepted__isnull=True,
    ).exists()
    if active_exists:
        return Response(
            {"detail": "An active invitation already exists for this email."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    invitation = SiteInvitation(
        email=data["email"],
        name=data.get("name", ""),
        inviter=request.user,
    )
    invitation.save()
    invitation.send_invitation(request)
    return Response(
        SiteInvitationSerializer(invitation).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAdminUser])
def bulk_invite(request):
    """Create a campaign and send invitations to a list of emails."""
    serializer = BulkInviteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    campaign = Campaign.objects.create(
        title=data["campaignTitle"],
        created_by=request.user,
    )

    existing_emails = set(
        SiteInvitation.objects.filter(
            email__in=data["emails"],
            accepted__isnull=True,
        ).values_list("email", flat=True)
    )

    created = []
    skipped = list(existing_emails)

    for email in data["emails"]:
        if email in existing_emails:
            continue
        invitation = SiteInvitation(
            email=email,
            name=data.get("name", ""),
            campaign=campaign,
            inviter=request.user,
        )
        invitation.save()
        invitation.send_invitation(request)
        created.append(invitation)

    return Response(
        {
            "campaign": CampaignSerializer(campaign).data,
            "created": SiteInvitationSerializer(created, many=True).data,
            "skipped": skipped,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["DELETE", "POST"])
@permission_classes([IsAdminUser])
def invitation_detail(request, key):
    """
    DELETE: revoke (delete) an invitation.
    POST:   resend an invitation, resetting its expiry.
    """
    try:
        invitation = SiteInvitation.objects.get(key=key)
    except SiteInvitation.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        invitation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # POST = resend
    if invitation.accepted:
        return Response(
            {"detail": "Invitation already accepted."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Reset sent timestamp so key_expired() recalculates from now
    invitation.sent = None
    invitation.save(update_fields=["sent"])
    invitation.send_invitation(request)
    return Response(SiteInvitationSerializer(invitation).data)
