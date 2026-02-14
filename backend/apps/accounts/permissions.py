from rest_framework.permissions import SAFE_METHODS, BasePermission


def _user_can_perform_clinical_actions(user) -> bool:
    """Doctor and Clinic Admin can perform clinical exams, close visits, medical records, etc."""
    if not (user and user.is_authenticated):
        return False
    role = getattr(user, "role", None)
    return role in ("doctor", "admin")


class IsVet(BasePermission):
    """
    Allows access only to authenticated users marked as vets.
    Deprecated: prefer IsDoctorOrAdmin. Kept for backward compatibility.
    """

    message = "Only vets can perform this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "is_vet", False))


class IsDoctorOrAdmin(BasePermission):
    """
    Allows access for Doctor and Clinic Admin roles.
    Required for: clinical exams, close visit, medical records, adding patient history.
    """

    message = "Only doctors and clinic admins can perform this action."

    def has_permission(self, request, view) -> bool:
        return _user_can_perform_clinical_actions(request.user)


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
    """
    Allows staff, superusers, vets, or any clinic role (doctor, receptionist, admin).
    Use for: appointments, inventory - all clinic personas can access.
    """

    message = "Only clinic staff can perform this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if getattr(user, "is_superuser", False):
            return True
        role = getattr(user, "role", None)
        if role in ("doctor", "receptionist", "admin"):
            return True
        return bool(getattr(user, "is_staff", False) or getattr(user, "is_vet", False))
