from rest_framework.permissions import BasePermission


class IsPortalClient(BasePermission):
    message = "Portal authentication required."

    def has_permission(self, request, view) -> bool:
        u = request.user
        return bool(u and u.is_authenticated and getattr(u, "is_portal", False))
