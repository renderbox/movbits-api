from django.contrib.auth.models import Permission
from django.contrib.sites.shortcuts import get_current_site
from django.db.models import Q
from rest_framework import viewsets

from ..models import FeatureFlag
from .serializers import FeatureFlagSerializer


class FeatureFlagViewSet(viewsets.ModelViewSet):
    serializer_class = FeatureFlagSerializer

    def get_queryset(self):
        current_site = get_current_site(self.request)
        qs = FeatureFlag.objects.filter(active=True, site=current_site)
        user = getattr(self.request, "user", None)

        if user and user.is_authenticated:
            perm_ids = Permission.objects.filter(
                Q(user=user) | Q(group__user=user)
            ).values_list("id", flat=True)
            return qs.filter(
                Q(permissions__isnull=True) | Q(permissions__in=perm_ids)
            ).distinct()

        return qs.filter(permissions__isnull=True)
