"""
Billing serializers.
"""

from rest_framework import serializers

from apps.clients.serializers import ClientSerializer
from apps.patients.serializers import PatientReadSerializer

from .models import Invoice, InvoiceLine, Payment, Service


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = [
            "id",
            "name",
            "code",
            "price",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class ServiceWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["name", "code", "price", "description"]


class InvoiceLineSerializer(serializers.ModelSerializer):
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = InvoiceLine
        fields = [
            "id",
            "description",
            "quantity",
            "unit_price",
            "line_total",
            "service",
            "inventory_item",
        ]

    def get_line_total(self, obj):
        return str(obj.line_total)


class InvoiceLineWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = [
            "description",
            "quantity",
            "unit_price",
            "service",
            "inventory_item",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "amount",
            "method",
            "status",
            "paid_at",
            "reference",
            "note",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class PaymentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["amount", "method", "status", "paid_at", "reference", "note"]


class InvoiceReadSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    client_detail = ClientSerializer(source="client", read_only=True)
    patient_detail = PatientReadSerializer(source="patient", read_only=True, allow_null=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "clinic",
            "client",
            "client_detail",
            "patient",
            "patient_detail",
            "appointment",
            "status",
            "due_date",
            "currency",
            "lines",
            "payments",
            "total",
            "amount_paid",
            "balance_due",
            "created_by",
            "created_at",
            "updated_at",
        ]


class InvoiceWriteSerializer(serializers.ModelSerializer):
    lines = InvoiceLineWriteSerializer(many=True, required=False)

    class Meta:
        model = Invoice
        fields = [
            "client",
            "patient",
            "appointment",
            "status",
            "due_date",
            "currency",
            "lines",
        ]

    def validate_patient(self, value):
        user = self.context["request"].user
        if value and value.clinic_id != getattr(user, "clinic_id", None):
            raise serializers.ValidationError("Patient must belong to your clinic.")
        return value

    def validate_client(self, value):
        user = self.context["request"].user
        if value:
            from apps.clients.models import ClientClinic
            if not ClientClinic.objects.filter(
                client=value, clinic_id=user.clinic_id, is_active=True
            ).exists():
                raise serializers.ValidationError(
                    "Client must be a member of your clinic."
                )
        return value

    def validate_appointment(self, value):
        user = self.context["request"].user
        if value and value.clinic_id != getattr(user, "clinic_id", None):
            raise serializers.ValidationError("Appointment must belong to your clinic.")
        return value

    def _validate_line(self, line_data, clinic_id):
        service = line_data.get("service")
        if service and service.clinic_id != clinic_id:
            raise serializers.ValidationError(
                {"lines": "Service must belong to your clinic."}
            )
        inv_item = line_data.get("inventory_item")
        if inv_item and inv_item.clinic_id != clinic_id:
            raise serializers.ValidationError(
                {"lines": "Inventory item must belong to your clinic."}
            )

    def create(self, validated_data):
        lines_data = validated_data.pop("lines", [])
        request = self.context["request"]
        clinic_id = request.user.clinic_id
        for line_data in lines_data:
            self._validate_line(line_data, clinic_id)
        invoice = Invoice.objects.create(
            clinic_id=clinic_id,
            created_by=request.user,
            **validated_data,
        )
        for line_data in lines_data:
            InvoiceLine.objects.create(invoice=invoice, **line_data)
        return invoice

    def update(self, instance, validated_data):
        if instance.status != Invoice.Status.DRAFT:
            raise serializers.ValidationError(
                {"status": "Only draft invoices can be edited."}
            )
        lines_data = validated_data.pop("lines", None)
        clinic_id = instance.clinic_id
        if lines_data is not None:
            for line_data in lines_data:
                self._validate_line(line_data, clinic_id)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if lines_data is not None:
            instance.lines.all().delete()
            for line_data in lines_data:
                InvoiceLine.objects.create(invoice=instance, **line_data)
        return instance
