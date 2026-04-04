from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasClinic, IsClinicAdmin, IsStaffOrVet
from apps.tenancy.access import clinic_id_for_mutation

from .models import Clinic
from .serializers import ClinicFeatureFlagsSerializer


class ClinicFeatureFlagsView(APIView):
    """
    GET: any staff with clinic access.
    PATCH: clinic admin only (same as other clinic settings).
    """

    def get_permissions(self):
        perms = [IsAuthenticated(), HasClinic()]
        if self.request.method == "GET":
            return perms + [IsStaffOrVet()]
        return perms + [IsClinicAdmin()]

    def get(self, request):
        cid = clinic_id_for_mutation(request.user, request=request, instance_clinic_id=None)
        clinic = Clinic.objects.get(pk=cid)
        return Response(ClinicFeatureFlagsSerializer(clinic).data)

    def patch(self, request):
        cid = clinic_id_for_mutation(request.user, request=request, instance_clinic_id=None)
        clinic = Clinic.objects.get(pk=cid)
        serializer = ClinicFeatureFlagsSerializer(clinic, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        clinic.refresh_from_db()
        return Response(ClinicFeatureFlagsSerializer(clinic).data)
