from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsStaffOrVet
from apps.tenancy.access import (
    accessible_clinic_ids,
)

from .models import Notification
from .serializers import NotificationReadSerializer


class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
    serializer_class = NotificationReadSerializer
    pagination_class = NotificationPagination

    def get_queryset(self):
        now = timezone.now()
        read_recent_cutoff = now - timedelta(days=7)
        return Notification.objects.filter(
            clinic_id__in=accessible_clinic_ids(self.request.user),
            recipient_id=self.request.user.id,
        ).filter(
            Q(is_read=False)
            | Q(
                is_read=True,
                read_at__gte=read_recent_cutoff,
            )
        )

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        obj = self.get_object()
        if not obj.is_read:
            obj.is_read = True
            obj.read_at = timezone.now()
            obj.save(update_fields=["is_read", "read_at"])
        return Response(self.get_serializer(obj).data, status=200)

    @action(detail=False, methods=["post"], url_path="read-all")
    def mark_read_all(self, request):
        now = timezone.now()
        updated = Notification.objects.filter(
            clinic_id__in=accessible_clinic_ids(request.user),
            recipient_id=request.user.id,
            is_read=False,
        ).update(is_read=True, read_at=now)
        return Response({"ok": True, "updated": updated}, status=200)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        count = Notification.objects.filter(
            clinic_id__in=accessible_clinic_ids(request.user),
            recipient_id=request.user.id,
            is_read=False,
        ).count()
        return Response({"count": count}, status=200)
