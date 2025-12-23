from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsVet(BasePermission):
    """
    Allows access only to authenticated users marked as vets.
    """

    message = "Only vets can perform this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "is_vet", False))


class HasClinic(BasePermission):
    """
    Allows access only to authenticated users that belong to a clinic.
    """

    message = "User must belong to a clinic."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "clinic_id", None))


class IsClinicStaffOrReadOnly(BasePermission):
    """
    Allows unsafe methods only for staff/superusers. Read-only for others.
    Useful for later if you expose read-only endpoints to non-staff users.
    """

    message = "Only staff can modify this resource."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))


class IsStaffOrVet(BasePermission):
    message = "Only staff or vets can perform this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return bool(
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or getattr(user, "is_vet", False)
        )
