# import re
import uuid

# from rest_framework_simplejwt.tokens import RefreshToken
from typing import Any, Dict  # , List

from dj_rest_auth.registration.views import RegisterView as RestAuthRegisterView
from dj_rest_auth.views import PasswordResetView as RestAuthPasswordResetView

# from dj_rest_auth.settings import api_settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import JsonResponse
from rest_framework import permissions, status, viewsets  # , generics
from rest_framework.decorators import action, api_view  # , permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated

# from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.serializers import (
    RegisterSerializer,
    SPAPasswordResetSerializer,
    UserConfigSerializer,
    UserUpdateSerializer,
)
from events.emit import TOPIC_AUDIT, emit
from events.schemas import AuthEvent
from history.models import ViewingHistory
from shows.models import Tag
from wallet.models import CreditTypes, Wallet

from ..models import FeatureFlag

# from rest_framework_simplejwt.settings import api_settings as jwt_settings


User = get_user_model()

# In-memory mock stores (dev only)
USERS: Dict[str, Dict[str, Any]] = {}
TEAMS: Dict[str, Dict[str, Any]] = {}


# Helper to create a default user
def _make_user(
    name: str = "Mock User", email: str = "user@example.com"
) -> Dict[str, Any]:
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "name": name,
        "email": email,
        "avatarUrl": None,
        "roles": ["user"],
        "createdAt": "2020-01-01T00:00:00Z",
        "profile": {
            "bio": "",
            "location": None,
        },
    }
    USERS[user_id] = user
    return user


# Helper to require Authorization header with Bearer mock token
def _require_auth(request: Request):
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.split(" ", 1)[1]
    # mock token format: "mock-token-<user_id>"
    if not token.startswith("mock-token-"):
        return None
    user_id = token[len("mock-token-") :]  # noqa: E203
    return USERS.get(user_id)


# Auth endpoints -------------------------------------------------------------


class UserViewSet(viewsets.ModelViewSet):
    """User Profile View to get and update user profile information"""

    queryset = User.objects.all()
    serializer_class = UserConfigSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"])
    def me(self, request):
        serializer = UserConfigSerializer(request.user, context={"request": request})
        return Response(serializer.data)


@api_view(["POST"])
def logout(request: Request):
    # In mock: there's nothing server-side to revoke.
    # This should log that the user logged out for auditing in a real app.
    return JsonResponse({"success": True})


class RegisterView(RestAuthRegisterView):
    """Use the custom registration serializer for dj-rest-auth."""

    serializer_class = RegisterSerializer


class PasswordResetView(RestAuthPasswordResetView):
    """Send password reset email with SPA link."""

    serializer_class = SPAPasswordResetSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[
            0
        ].strip() or request.META.get("REMOTE_ADDR", "")
        emit(
            TOPIC_AUDIT,
            AuthEvent(
                event_type="auth.password_reset_requested",
                email=request.data.get("email"),
                ip_address=ip,
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            ),
        )
        return response


# Needed Views
@api_view(["POST"])
def signup(request: Request):
    # TODO: In real app, validate input, hash password, etc.
    body = request.data

    # Will body always be a dict?
    if not isinstance(body, dict):
        return JsonResponse(
            {"error": "Invalid request body"}, status=status.HTTP_400_BAD_REQUEST
        )

    email = body.get("email", None)

    if not email:
        return JsonResponse(
            {"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST
        )

    name = body.get("name") or email.split("@")[0]
    # Naive uniqueness: if exists, return it
    existing = next((u for u in USERS.values() if u.get("email") == email), None)
    if existing:
        user = existing
    else:
        user = _make_user(name=name, email=email)
    token = f"mock-token-{user['id']}"
    refresh = f"mock-refresh-{user['id']}"
    return JsonResponse(
        {"token": token, "refreshToken": refresh, "user": user},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
def verify_2fa(request: Request):
    """
    Verifies a TOTP code for the authenticated user.
    Used as a step-up check after password login when MFA is required.
    Full login-flow integration (issuing JWT post-verification) is a
    separate concern handled by the auth pipeline.
    """
    if not request.user.is_authenticated:
        return JsonResponse(
            {"detail": "Authentication required."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    code = (request.data or {}).get("code", "").strip()
    if not code:
        return JsonResponse(
            {"detail": "code is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from allauth.mfa.models import Authenticator
    from allauth.mfa.totp.internal.auth import TOTP

    try:
        authenticator = Authenticator.objects.get(
            user=request.user, type=Authenticator.Type.TOTP
        )
    except Authenticator.DoesNotExist:
        return JsonResponse(
            {"detail": "Two-factor authentication is not configured."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    totp = TOTP(authenticator)
    if not totp.validate_code(code):
        return JsonResponse(
            {"detail": "Invalid code."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    authenticator.record_usage()
    return JsonResponse({"success": True})


# TODO: Password Reset View for users who forgot their password
@api_view(["POST"])
def password_reset_request(request: Request):

    if not isinstance(request.data, dict):
        return JsonResponse(
            {"error": "Invalid request body"}, status=status.HTTP_400_BAD_REQUEST
        )

    # email = request.data.get("email", None)
    # even if email not found, we return success to avoid user enumeration

    # log a password reset request to the security log if the email does not exist in a real app

    # In a real app we would email a token. Here we return a dummy success.
    return JsonResponse({"success": True})


@api_view(["POST"])
def password_reset_confirm(request: Request):

    if not isinstance(request.data, dict):
        return JsonResponse(
            {"error": "Invalid request body"}, status=status.HTTP_400_BAD_REQUEST
        )

    token = request.data.get("token")
    new_password = request.data.get("newPassword")
    if token and new_password:
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[
            0
        ].strip() or request.META.get("REMOTE_ADDR", "")
        emit(
            TOPIC_AUDIT,
            AuthEvent(
                event_type="auth.password_reset_completed",
                ip_address=ip,
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            ),
        )
        return JsonResponse({"success": True})
    return JsonResponse({"success": False}, status=status.HTTP_400_BAD_REQUEST)


# TODO: TFA Setup View for users to setup their two factor authentication

# TODO: Get Profile View to get user profile information who is not the current user and has permission
# path('users/<int:user_id>', users.get_user, name='get_user'),

# TODO: Update Profile View for users to update their profile information
# path('users/profile/update', users.update_profile, name='update_profile'),

# Teams Endpoints.  Teams are created by site admins and managed by team admins.


# User endpoints -------------------------------------------------------------
class CurrentFeaturesView(APIView):
    """
    Returns the current feature flags for the user.
    """

    def get(self, request):
        if not request.user.is_authenticated:
            features = {
                flag.key: flag.get_value()
                for flag in FeatureFlag.objects.filter(
                    permissions__isnull=True,  # only include flags that have no permissions
                    is_active=True,
                    sites=request.site,
                ).distinct()
            }
        else:
            features = {
                flag.key: flag.get_value()
                for flag in FeatureFlag.objects.filter(
                    Q(permissions__in=request.user.user_permissions.all())
                    | Q(permissions__isnull=True),
                    is_active=True,
                    sites=request.site,
                ).distinct()
            }

            if (
                request.user.is_superuser
            ):  # if the user is a django admin, add adminTools: true to the response
                features["adminTools"] = True

        return Response(features)


class CurrentUserView(APIView):
    """
    Mocked data (from the SPA):
    const user = {
        name: "John Doe",
        email: "john.doe@example.com",
        avatar: "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=400&h=400&fit=crop&crop=face",
        joinDate: "March 2023",
        credits: 12,
        totalWatched: 156,
        favoriteGenre: "Action",
        watchTime: "142 hours"
    };

    """

    def get(self, request):

        isAdmin = False
        isCreator = False
        role = "member"

        # Need to map this to key/value pair like this:
        # TODO: if a flag does not have permissions, it should be available to all users.  If a flag has permissions, it should only be available to users with those permissions.
        features = {
            flag.key: flag.get_value()
            for flag in FeatureFlag.objects.filter(
                Q(permissions__in=request.user.user_permissions.all())
                | Q(permissions__isnull=True),
                is_active=True,
                sites=request.site,
            ).distinct()
        }

        if not request.user.is_authenticated:
            return Response(
                {
                    "isAuthenticated": False,
                    "features": features,
                }
            )

        # lets update this to check if the user is a member of a group
        if request.user.groups.filter(name="Creator").exists():
            isCreator = True

        if isCreator:
            role = "creator"

        # if the user is a django admin, add isAdmin: true to the response
        if request.user.is_superuser:
            role = "admin"
            isAdmin = True
            features["adminTools"] = True

        # get or create the user's "credit" wallet so we can use the balance.
        wallet, _ = Wallet.objects.get_or_create(
            user=request.user, site=request.site, credit_type=CreditTypes.CREDIT
        )

        current_user = {
            "id": request.user.id,
            "name": request.user.get_full_name(),
            "email": request.user.email,
            "avatar": (
                request.build_absolute_uri(request.user.avatar.url)
                if request.user.avatar
                else ""
            ),
            "role": role,
            "isAdmin": isAdmin,
            "isCreator": isCreator,
            "status": "active",
            "joinDate": request.user.date_joined.strftime(
                "%Y-%m-%d"
            ),  # Format the date_joined field
            "lastActive": request.user.last_login.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),  # Format the last_login field
            "credits": wallet.balance,
            "stripeCustomerId": request.user.stripe_customer_id,
            "subscription": "premium",
            "previewMode": features.get("previewMode", False),
            "twoFactorEnabled": True,
            "totalWatched": 15600,
            "favoriteGenre": "Action",
            "watchTime": "142 hours",
            "minutesWatchedThisWeek": 1024,
            "watchStreak": 128,
            "features": features,  # TODO: move this to the CurrentFeaturesView endpoint and remove it from here
        }
        return Response(current_user)

    def patch(self, request):
        serializer = UserUpdateSerializer(
            request.user, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Return the updated config view to match existing "me" payload
        config = UserConfigSerializer(request.user, context={"request": request})
        return Response(config.data)


class AvatarUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def patch(self, request):
        avatar_file = request.FILES.get("avatar")
        if not avatar_file:
            return Response(
                {"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST
            )
        request.user.avatar = avatar_file
        request.user.save(update_fields=["avatar"])
        config = UserConfigSerializer(request.user, context={"request": request})
        return Response(config.data)


class UserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id: str):

        # get the user from the request.  The user ID is passed in the URL.
        user = User.objects.get(id=user_id)

        current_user = {
            "id": user.id,
            "name": user.get_full_name(),
            "email": user.email,
            "avatar": "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=400&h=400&fit=crop&crop=face",
            "role": "creator",
            "status": "active",
            "joinDate": "2024-01-01",
            "lastActive": "2025-10-29T10:30:00Z",
            "credits": 2000,
            "subscription": "premium",
            "previewMode": True,
            "twoFactorEnabled": True,
        }
        return Response(current_user)


class UserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id: str):

        # get the user from the request.  The user ID is passed in the URL.
        user = User.objects.get(id=user_id)

        current_user = {
            "id": user.id,
            "name": user.get_full_name(),
            "email": user.email,
            "avatar": "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=100&h=100&fit=crop&crop=face",
            "role": "creator",
            "status": "active",
            "joinDate": "2024-01-01",
            "lastActive": "2025-10-29T10:30:00Z",
            "credits": 2000,
            "subscription": "premium",
            "previewMode": True,
            "twoFactorEnabled": True,
        }
        return Response(current_user)

    def post(self, request: Request):
        # Handle POST request for user creation
        pass


@api_view(["GET", "POST"])
def users_list(request: Request):
    """STUB:

    export const users: User[] = [
    currentUser,
    {
        id: 'user-2',
        name: 'Alice Johnson',
        email: 'alice@example.com',
        avatar: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100&h=100&fit=crop&crop=face',
        role: 'creator',
        status: 'active',
        joinDate: '2024-01-15',
        credits: 200,
        subscription: 'pro',
    },
    {
        id: 'user-3',
        name: 'Bob Wilson',
        email: 'bob@example.com',
        avatar: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=100&h=100&fit=crop&crop=face',
        role: 'viewer',
        status: 'active',
        joinDate: '2024-01-14',
        credits: 50,
        subscription: 'free',
    },
    {
        id: 'user-4',
        name: 'Carol Smith',
        email: 'carol@example.com',
        avatar: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=100&h=100&fit=crop&crop=face',
        role: 'creator',
        status: 'pending',
        joinDate: '2024-01-13',
        credits: 0,
        subscription: 'free',
    },
    {
        id: 'user-5',
        name: 'David Brown',
        email: 'david@example.com',
        avatar: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&h=100&fit=crop&crop=face',
        role: 'viewer',
        status: 'suspended',
        joinDate: '2024-01-12',
        credits: 0,
        subscription: 'free',
    },
    ];
    """

    # GET: list users, POST: create (admin-only in real app)
    if request.method == "GET":
        # Allow public listing only when authenticated for this mock
        auth_user = _require_auth(request)
        if not auth_user:
            return JsonResponse(
                {"detail": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return JsonResponse(list(USERS.values()), safe=False)
    else:
        body = request.data
        name = body.get("name", "New User")
        email = body.get("email", f"new+{uuid.uuid4().hex[:6]}@example.com")
        user = _make_user(name=name, email=email)
        return JsonResponse(user, status=status.HTTP_201_CREATED)


@api_view(["PUT"])
def update_profile(request: Request):
    """STUB:"""
    auth_user = _require_auth(request)
    if not auth_user:
        return JsonResponse(
            {"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED
        )
    data = request.data
    # update allowed fields naively
    auth_user.update(
        {k: v for k, v in data.items() if k in ("name", "avatarUrl", "profile")}
    )
    return JsonResponse(auth_user)


@api_view(["GET"])
def get_credits(request: Request):
    """STUB:"""
    auth_user = _require_auth(request)
    if not auth_user:
        return JsonResponse(
            {"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED
        )
    # Mock balance and history
    return JsonResponse({"balance": 100, "history": []})


def _format_duration(seconds: int) -> str:
    """Convert a duration in seconds to a human-readable string like '1h 32m'."""
    if not seconds:
        return ""
    minutes = seconds // 60
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def _format_watched_at(dt) -> str:
    """Return a relative time string like '2 hours ago'."""
    from django.utils import timezone
    from django.utils.timesince import timesince

    return f"{timesince(dt, now=timezone.now())} ago"


@api_view(["GET"])
def get_history_recent(request: Request):
    """Returns the authenticated user's recently watched episodes."""
    entries = (
        ViewingHistory.objects.filter(user=request.user)
        .select_related("episode", "episode__show")
        .prefetch_related("episode__show__tags")
        .order_by("-watched_at")[:50]
    )

    result = []
    for entry in entries:
        episode = entry.episode
        show = episode.show
        genre_tag = show.tags.filter(tagtype=Tag.TagType.GENRE).first()
        rating_raw = episode.rating_value
        result.append(
            {
                "id": episode.slug,
                "title": episode.title,
                "poster": show.poster_url or "",
                "duration": _format_duration(episode.duration),
                "rating": round(rating_raw / 10, 1) if rating_raw is not None else None,
                "genre": genre_tag.name if genre_tag else "",
                "watchedAt": _format_watched_at(entry.watched_at),
                "progress": entry.progress,
            }
        )

    return Response(result)


@api_view(["GET"])
def get_history_favorite(request: Request):
    """STUB: Returns the user's favorite videos."""

    favorites = [
        {
            "id": "fav-1",
            "title": "Space Odyssey",
            "poster": "https://images.unsplash.com/photo-1446776653964-20c1d3a81b06?w=400&h=600&fit=crop",
            "duration": "2h 5m",
            "rating": 4.9,
            "genre": "Sci-Fi",
            "watchedAt": "1 week ago",
            "description": "Stunning documentary series exploring the most beautiful places on Earth.",
            "progress": 100,
        },
        {
            "id": "fav-2",
            "title": "Epic Adventure Chronicles",
            "poster": "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=400&h=600&fit=crop",
            "duration": "2h 15m",
            "rating": 4.8,
            "genre": "Adventure",
            "watchedAt": "2 hours ago",
            "progress": 75,
        },
        {
            "id": "fav-3",
            "title": "Ocean Deep",
            "poster": "https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=400&h=600&fit=crop",
            "duration": "1h 32m",
            "rating": 4.7,
            "genre": "Documentary",
            "watchedAt": "3 days ago",
            "progress": 45,
        },
    ]
    return Response(favorites)


#


@api_view(["GET"])
def get_devices(request: Request):
    """STUB: Returns the user's devices."""

    result = [
        {
            "id": "d1",
            "name": "iPhone 15 Pro",
            "type": "mobile",
            "lastActive": "Active now",
            "current": True,
        },
        {
            "id": "d2",
            "name": "MacBook Pro",
            "type": "desktop",
            "lastActive": "2 hours ago",
            "current": False,
        },
        {
            "id": "d3",
            "name": "iPad Air",
            "type": "tablet",
            "lastActive": "1 day ago",
            "current": False,
        },
    ]

    return Response(result)


#   const mockHistory: HistoryItem[] = [
#     {
#       id: 'h1',
#       title: 'The Space Chronicles',
#       type: 'episode',
#       thumbnail: 'https://images.unsplash.com/photo-1446776653964-20c1d3a81b06?w=400&h=225&fit=crop',
#       progress: 75,
#       duration: '42m',
#       lastWatched: '2 hours ago',
#       showTitle: 'Cosmic Journeys',
#       episodeNumber: 'S2 E8'
#     },
#     {
#       id: 'h2',
#       title: 'Digital Frontiers',
#       type: 'movie',
#       thumbnail: 'https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=400&h=225&fit=crop',
#       progress: 100,
#       duration: '2h 15m',
#       lastWatched: '1 day ago'
#     },
#     {
#       id: 'h3',
#       title: 'Ocean Mysteries',
#       type: 'episode',
#       thumbnail: 'https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=400&h=225&fit=crop',
#       progress: 30,
#       duration: '38m',
#       lastWatched: '2 days ago',
#       showTitle: 'Nature Documentaries',
#       episodeNumber: 'S1 E3'
#     },
#     {
#       id: 'h4',
#       title: 'City of Tomorrow',
#       type: 'movie',
#       thumbnail: 'https://images.unsplash.com/photo-1519501025264-65ba15a82390?w=400&h=225&fit=crop',
#       progress: 15,
#       duration: '1h 58m',
#       lastWatched: '3 days ago'
#     }
#   ];

#   const watchlistItems: WatchlistItem[] = [
#     {
#       id: 'w1',
#       title: 'Future Wars',
#       thumbnail: 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=200&h=300&fit=crop',
#       type: 'series',
#       addedDate: '2 days ago'
#     },
#     {
#       id: 'w2',
#       title: 'Silent Earth',
#       thumbnail: 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=200&h=300&fit=crop',
#       type: 'movie',
#       addedDate: '1 week ago'
#     },
#     {
#       id: 'w3',
#       title: 'Tech Revolution',
#       thumbnail: 'https://images.unsplash.com/photo-1485846234645-a62644f84728?w=200&h=300&fit=crop',
#       type: 'series',
#       addedDate: '2 weeks ago'
#     }
#   ];

#   const devices: Device[] = [
#     {
#       id: 'd1',
#       name: 'iPhone 15 Pro',
#       type: 'mobile',
#       lastActive: 'Active now',
#       current: true
#     },
#     {
#       id: 'd2',
#       name: 'MacBook Pro',
#       type: 'desktop',
#       lastActive: '2 hours ago',
#       current: false
#     },
#     {
#       id: 'd3',
#       name: 'iPad Air',
#       type: 'tablet',
#       lastActive: '1 day ago',
#       current: false
#     }
#   ];


"""
  const watchListItems: WatchListItem[] = [
    {
      id: 'watchlist-1',
      title: 'Epic Adventure Chronicles',
      poster: 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=400&h=600&fit=crop',
      duration: '2h 15m',
      rating: 4.8,
      genre: 'Adventure',
      type: 'video',
      addedAt: '2 days ago',
      isLocked: false,
      description: 'Join our heroes on an unforgettable journey through mystical lands filled with danger and wonder.'
    },
    {
      id: 'watchlist-2',
      title: 'Shadow Warriors',
      poster: 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=400&h=600&fit=crop',
      duration: '24 episodes',
      rating: 4.8,
      genre: 'Action',
      type: 'series',
      addedAt: '1 week ago',
      isLocked: false,
      description: 'Elite warriors battle in the shadows to protect the innocent.',
      episodes: 24,
      seasons: 3
    },
    {
      id: 'watchlist-3',
      title: 'City Lights Mystery',
      poster: 'https://images.unsplash.com/photo-1707300235625-3d7f9fe69475?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxjaXR5JTIwbGlnaHRzJTIwbmlnaHQlMjBteXN0ZXJ5fGVufDF8fHx8MTc2MDQ2ODc0N3ww&ixlib=rb-4.1.0&q=80&w=1080',  # noqa: E501
      duration: '1h 45m',
      rating: 4.6,
      genre: 'Thriller',
      type: 'video',
      addedAt: '3 days ago',
      isLocked: true,
      description: 'A gripping thriller set in the neon-lit streets of a bustling metropolis.'
    },
    {
      id: 'watchlist-4',
      title: 'Nature\'s Wonders',
      poster: 'https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=400&h=600&fit=crop',
      duration: '12 episodes',
      rating: 4.8,
      genre: 'Documentary',
      type: 'series',
      addedAt: '5 days ago',
      isLocked: false,
      description: 'Stunning documentary series exploring the most beautiful places on Earth.',
      episodes: 12,
      seasons: 2
    },
    {
      id: 'watchlist-5',
      title: 'Space Odyssey',
      poster: 'https://images.unsplash.com/photo-1446776653964-20c1d3a81b06?w=400&h=600&fit=crop',
      duration: '2h 5m',
      rating: 4.9,
      genre: 'Sci-Fi',
      type: 'video',
      addedAt: '1 week ago',
      isLocked: true,
      description: 'An interstellar journey through the cosmos.'
    },
    {
      id: 'watchlist-6',
      title: 'Office Shenanigans',
      poster: 'https://images.unsplash.com/photo-1485846234645-a62644f84728?w=400&h=600&fit=crop',
      duration: '30 episodes',
      rating: 4.6,
      genre: 'Comedy',
      type: 'series',
      addedAt: '2 weeks ago',
      isLocked: false,
      description: 'Hilarious workplace comedy following the daily antics of a quirky office team.',
      episodes: 30,
      seasons: 5
    }
  ];



"""


@api_view(["GET"])
def get_tos(request: Request):
    # TODO: return the Terms of Service for use in the App. return it in the relevant language if available

    result = {"title": "Terms of Service"}

    return Response(result)


@api_view(["GET"])
def get_eula(request: Request):
    # TODO: return the Terms of Service for use in the App

    result = {"title": "End User License Agreement"}

    return Response(result)


@api_view(["GET"])
def get_about(request: Request):
    # TODO: return the Terms of Service for use in the App

    result = {"title": "About Us"}

    return Response(result)


# ── SSO providers ─────────────────────────────────────────────────────────────

_ALL_SSO_PROVIDERS = [
    {
        "id": "google",
        "name": "Google",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "scope": "profile email",
    },
    {
        "id": "facebook",
        "name": "Facebook",
        "auth_url": "https://www.facebook.com/v18.0/dialog/oauth",
        "scope": "email,public_profile",
    },
    {
        "id": "instagram",
        "name": "Instagram",
        "auth_url": "https://api.instagram.com/oauth/authorize",
        "scope": "user_profile",
    },
    {
        "id": "tiktok",
        "name": "TikTok",
        "auth_url": "https://www.tiktok.com/v2/auth/authorize/",
        "scope": "user.info.basic",
    },
]


@api_view(["GET"])
def sso_providers(request: Request):
    """
    Return the list of SSO providers and whether each is currently enabled.

    A provider is enabled when:
      1. Its ID is listed in SSO_ENABLED_PROVIDERS (the feature flag), AND
      2. A SocialApp record exists in the DB for that provider (credentials
         are managed via Django admin → Social Applications).

    For enabled providers the response includes client_id and auth_url so the
    frontend can construct the OAuth redirect URL without hardcoding anything.
    """
    from allauth.socialaccount.models import SocialApp
    from django.conf import settings

    enabled_flag = set(getattr(settings, "SSO_ENABLED_PROVIDERS", []))

    # Fetch all relevant SocialApp records in one query
    provider_ids = [p["id"] for p in _ALL_SSO_PROVIDERS]
    social_apps = {
        app.provider: app for app in SocialApp.objects.filter(provider__in=provider_ids)
    }

    providers = []
    for p in _ALL_SSO_PROVIDERS:
        app = social_apps.get(p["id"])
        is_enabled = p["id"] in enabled_flag and app is not None
        entry = {"id": p["id"], "name": p["name"], "enabled": is_enabled}
        if is_enabled:
            entry["auth_url"] = p["auth_url"]
            entry["scope"] = p["scope"]
            entry["client_id"] = app.client_id
        providers.append(entry)

    return Response({"providers": providers})
