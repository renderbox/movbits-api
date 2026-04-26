from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from support.models import (
    SenderRole,
    SupportTicket,
    TicketMessage,
    TicketPriority,
    TicketStatus,
)

User = get_user_model()


def make_user(username="user", is_staff=False):
    u = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="password",
        is_staff=is_staff,
    )
    return u


def make_ticket(user, subject="Issue", description="Desc", status=TicketStatus.OPEN):
    t = SupportTicket.objects.create(
        user=user, subject=subject, description=description, status=status
    )
    TicketMessage.objects.create(
        ticket=t, sender=user, sender_role=SenderRole.USER, message=description
    )
    return t


# ── tickets_list ──────────────────────────────────────────────────────────────


class TicketsListTests(APITestCase):
    def setUp(self):
        self.user = make_user("alice")
        self.other = make_user("bob")
        self.ticket = make_ticket(self.user, "Alice issue")
        make_ticket(self.other, "Bob issue")

    def test_unauthenticated_returns_401(self):
        response = self.client.get(reverse("tickets_list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_only_own_tickets(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("tickets_list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["subject"], "Alice issue")

    def test_create_ticket(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            reverse("tickets_list"),
            {
                "subject": "New issue",
                "description": "Something broke.",
                "category": "technical",
                "priority": "high",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["subject"], "New issue")
        self.assertEqual(response.data["userId"], str(self.user.pk))

    def test_create_ticket_creates_initial_message(self):
        self.client.force_authenticate(self.user)
        self.client.post(
            reverse("tickets_list"),
            {"subject": "Msg test", "description": "Initial message body."},
            format="json",
        )
        ticket = SupportTicket.objects.get(subject="Msg test")
        self.assertEqual(ticket.messages.count(), 1)
        self.assertEqual(ticket.messages.first().message, "Initial message body.")

    def test_create_ticket_missing_subject_returns_400(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            reverse("tickets_list"), {"description": "No subject."}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ── admin_tickets_list ────────────────────────────────────────────────────────


class AdminTicketsListTests(APITestCase):
    def setUp(self):
        self.user = make_user("user1")
        self.staff = make_user("staff1", is_staff=True)
        make_ticket(self.user, "User ticket", status=TicketStatus.OPEN)
        make_ticket(self.user, "Resolved ticket", status=TicketStatus.RESOLVED)

    def test_non_staff_returns_403(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("admin_tickets_list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_sees_all_tickets(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(reverse("admin_tickets_list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_filter_by_status(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(reverse("admin_tickets_list") + "?status=resolved")
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["status"], "resolved")

    def test_search_filter(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(reverse("admin_tickets_list") + "?search=Resolved")
        self.assertEqual(len(response.data), 1)


# ── ticket_detail ─────────────────────────────────────────────────────────────


class TicketDetailTests(APITestCase):
    def setUp(self):
        self.user = make_user("alice")
        self.other = make_user("bob")
        self.staff = make_user("staff", is_staff=True)
        self.ticket = make_ticket(self.user)

    def test_owner_can_get_ticket(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.ticket.pk)

    def test_other_user_gets_404(self):
        self.client.force_authenticate(self.other)
        response = self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_staff_can_get_any_ticket(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_includes_messages(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        self.assertIn("messages", response.data)
        self.assertEqual(len(response.data["messages"]), 1)

    def test_owner_can_delete_ticket(self):
        self.client.force_authenticate(self.user)
        response = self.client.delete(reverse("ticket_detail", args=[self.ticket.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(SupportTicket.objects.filter(pk=self.ticket.pk).exists())


# ── ticket_messages ───────────────────────────────────────────────────────────


class TicketMessagesTests(APITestCase):
    def setUp(self):
        self.user = make_user("alice")
        self.staff = make_user("staff", is_staff=True)
        self.ticket = make_ticket(self.user)

    def test_get_messages(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("ticket_add_message", args=[self.ticket.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_user_can_post_message(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            reverse("ticket_add_message", args=[self.ticket.pk]),
            {"message": "Follow-up question."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["senderRole"], "user")

    def test_staff_message_has_support_role(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(
            reverse("ticket_add_message", args=[self.ticket.pk]),
            {"message": "We are looking into this."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["senderRole"], "support")

    def test_post_message_missing_body_returns_400(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            reverse("ticket_add_message", args=[self.ticket.pk]),
            {"message": ""},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_message_with_attachments(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            reverse("ticket_add_message", args=[self.ticket.pk]),
            {
                "message": "See attached.",
                "attachments": [
                    {"url": "https://example.com/file.png", "filename": "file.png"}
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["attachments"]), 1)
        self.assertEqual(response.data["attachments"][0]["filename"], "file.png")


# ── ticket_update_status / priority / assign ──────────────────────────────────


class TicketAdminActionsTests(APITestCase):
    def setUp(self):
        self.user = make_user("alice")
        self.staff = make_user("staff", is_staff=True)
        self.ticket = make_ticket(self.user)

    def test_non_staff_cannot_update_status(self):
        self.client.force_authenticate(self.user)
        response = self.client.put(
            reverse("ticket_update_status", args=[self.ticket.pk]),
            {"status": "resolved"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_update_status(self):
        self.client.force_authenticate(self.staff)
        response = self.client.put(
            reverse("ticket_update_status", args=[self.ticket.pk]),
            {"status": "in-progress"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, TicketStatus.IN_PROGRESS)

    def test_staff_can_update_priority(self):
        self.client.force_authenticate(self.staff)
        response = self.client.put(
            reverse("ticket_update_priority", args=[self.ticket.pk]),
            {"priority": "urgent"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.priority, TicketPriority.URGENT)

    def test_staff_can_assign_ticket(self):
        self.client.force_authenticate(self.staff)
        response = self.client.put(
            reverse("ticket_assign", args=[self.ticket.pk]),
            {"agentId": self.staff.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.assigned_to, self.staff)

    def test_staff_can_unassign_ticket(self):
        self.ticket.assigned_to = self.staff
        self.ticket.save()
        self.client.force_authenticate(self.staff)
        response = self.client.put(
            reverse("ticket_assign", args=[self.ticket.pk]),
            {"agentId": None},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.assigned_to)


# ── ticket_close / reopen ─────────────────────────────────────────────────────


class TicketCloseReopenTests(APITestCase):
    def setUp(self):
        self.user = make_user("alice")
        self.other = make_user("bob")
        self.ticket = make_ticket(self.user)

    def test_owner_can_close_ticket(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            reverse("ticket_close", args=[self.ticket.pk]),
            {"resolution": "Fixed it."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, TicketStatus.CLOSED)
        self.assertEqual(self.ticket.resolution, "Fixed it.")

    def test_other_user_cannot_close_ticket(self):
        self.client.force_authenticate(self.other)
        response = self.client.post(
            reverse("ticket_close", args=[self.ticket.pk]), {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_reopen_ticket(self):
        self.ticket.status = TicketStatus.CLOSED
        self.ticket.save()
        self.client.force_authenticate(self.user)
        response = self.client.post(
            reverse("ticket_reopen", args=[self.ticket.pk]), {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, TicketStatus.IN_PROGRESS)


# ── tickets_stats ─────────────────────────────────────────────────────────────


class TicketsStatsTests(APITestCase):
    def setUp(self):
        self.user = make_user("alice")
        self.staff = make_user("staff", is_staff=True)
        make_ticket(self.user, status=TicketStatus.OPEN)
        make_ticket(self.user, status=TicketStatus.RESOLVED)
        make_ticket(self.user, status=TicketStatus.CLOSED)

    def test_non_staff_returns_403(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("tickets_stats"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_stats_shape_and_counts(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(reverse("tickets_stats"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["total"], 3)
        self.assertEqual(data["open"], 1)
        self.assertEqual(data["resolved"], 1)
        self.assertEqual(data["closed"], 1)
        self.assertIn("averageResolutionTime", data)


# ── tickets_search ────────────────────────────────────────────────────────────


class TicketsSearchTests(APITestCase):
    def setUp(self):
        self.user = make_user("alice")
        make_ticket(self.user, "Login problem", "Can't log in")
        make_ticket(self.user, "Billing question", "Charged twice")

    def test_search_returns_matching_tickets(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("tickets_search") + "?q=login")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["subject"], "Login problem")

    def test_empty_query_returns_empty_list(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("tickets_search"))
        self.assertEqual(response.data, [])


# ── tickets_unread_count ──────────────────────────────────────────────────────


class TicketsUnreadCountTests(APITestCase):
    def setUp(self):
        self.user = make_user("alice")
        self.staff = make_user("staff", is_staff=True)
        self.ticket = make_ticket(self.user)

    def test_zero_when_no_support_reply(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("tickets_unread_count"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_increments_when_support_replies(self):
        TicketMessage.objects.create(
            ticket=self.ticket,
            sender=self.staff,
            sender_role=SenderRole.SUPPORT,
            message="We're looking into it.",
        )
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("tickets_unread_count"))
        self.assertEqual(response.data["count"], 1)
