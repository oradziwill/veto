"""
Billing serializers.
"""

from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from apps.clients.serializers import ClientSerializer
from apps.inventory.models import InventoryMovement
from apps.inventory.services.stock import apply_movement
from apps.patients.serializers import PatientReadSerializer
from apps.tenancy.access import (
    accessible_clinic_ids,
    clinic_id_for_mutation,
    user_can_access_clinic,
)

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
    line_vat_amount = serializers.SerializerMethodField()
    line_gross = serializers.SerializerMethodField()

    class Meta:
        model = InvoiceLine
        fields = [
            "id",
            "description",
            "quantity",
            "unit_price",
            "vat_rate",
            "unit",
            "line_total",
            "line_vat_amount",
            "line_gross",
            "service",
            "inventory_item",
        ]

    def get_line_total(self, obj):
        return str(obj.line_total)

    def get_line_vat_amount(self, obj):
        return str(obj.line_vat_amount)

    def get_line_gross(self, obj):
        return str(obj.line_gross)


class InvoiceLineWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = [
            "description",
            "quantity",
            "unit_price",
            "vat_rate",
            "unit",
            "service",
            "inventory_item",
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        inventory_item = attrs.get("inventory_item")
        quantity = attrs.get("quantity")
        if inventory_item is not None and quantity is not None:
            if Decimal(quantity) != Decimal(quantity).to_integral_value():
                raise serializers.ValidationError(
                    {"quantity": "quantity must be a whole number when inventory_item is set."}
                )
        return attrs


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
    total_gross = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
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
            "invoice_number",
            "due_date",
            "currency",
            "ksef_number",
            "ksef_status",
            "lines",
            "payments",
            "total",
            "total_gross",
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
            "invoice_number",
            "due_date",
            "currency",
            "lines",
        ]

    def validate_patient(self, value):
        user = self.context["request"].user
        if value and not user_can_access_clinic(user, value.clinic_id):
            raise serializers.ValidationError("Patient must belong to your clinic.")
        return value

    def validate_client(self, value):
        user = self.context["request"].user
        if value:
            from apps.clients.models import ClientClinic

            ids = accessible_clinic_ids(user)
            if not ClientClinic.objects.filter(
                client=value, clinic_id__in=ids, is_active=True
            ).exists():
                raise serializers.ValidationError("Client must be a member of your clinic.")
        return value

    def validate_appointment(self, value):
        user = self.context["request"].user
        if value and not user_can_access_clinic(user, value.clinic_id):
            raise serializers.ValidationError("Appointment must belong to your clinic.")
        return value

    def _validate_line(self, line_data, clinic_id):
        service = line_data.get("service")
        if service and service.clinic_id != clinic_id:
            raise serializers.ValidationError({"lines": "Service must belong to your clinic."})
        inv_item = line_data.get("inventory_item")
        if inv_item and inv_item.clinic_id != clinic_id:
            raise serializers.ValidationError(
                {"lines": "Inventory item must belong to your clinic."}
            )

    @staticmethod
    def _movement_note(*, appointment_id: int, invoice_id: int, line_id: int) -> str:
        return f"Dispensed in visit #{appointment_id} (invoice #{invoice_id}, line #{line_id})"

    def _create_dispense_movement_if_needed(
        self, *, invoice: Invoice, line: InvoiceLine, request_user
    ) -> None:
        if not invoice.appointment_id or not line.inventory_item_id:
            return
        quantity = int(Decimal(line.quantity))
        if quantity <= 0:
            return
        note = self._movement_note(
            appointment_id=invoice.appointment_id,
            invoice_id=invoice.id,
            line_id=line.id,
        )
        # Idempotency guard in case serializer.save() is retried.
        existing = InventoryMovement.objects.filter(
            clinic_id=invoice.clinic_id,
            item_id=line.inventory_item_id,
            kind=InventoryMovement.Kind.OUT,
            quantity=quantity,
            appointment_id=invoice.appointment_id,
            note=note,
        ).exists()
        if existing:
            return
        movement = InventoryMovement.objects.create(
            clinic_id=invoice.clinic_id,
            item_id=line.inventory_item_id,
            kind=InventoryMovement.Kind.OUT,
            quantity=quantity,
            note=note,
            patient_id=invoice.patient_id,
            appointment_id=invoice.appointment_id,
            created_by=request_user,
        )
        try:
            apply_movement(movement)
        except ValueError as err:
            raise serializers.ValidationError({"lines": [str(err)]}) from err

    def create(self, validated_data):
        lines_data = validated_data.pop("lines", [])
        request = self.context["request"]
        clinic_id = clinic_id_for_mutation(request.user, request=request, instance_clinic_id=None)
        for line_data in lines_data:
            self._validate_line(line_data, clinic_id)
        with transaction.atomic():
            invoice = Invoice.objects.create(
                clinic_id=clinic_id,
                created_by=request.user,
                **validated_data,
            )
            for line_data in lines_data:
                line = InvoiceLine.objects.create(invoice=invoice, **line_data)
                self._create_dispense_movement_if_needed(
                    invoice=invoice,
                    line=line,
                    request_user=request.user,
                )
        return invoice

    def update(self, instance, validated_data):
        if instance.status != Invoice.Status.DRAFT:
            raise serializers.ValidationError({"status": "Only draft invoices can be edited."})
        lines_data = validated_data.pop("lines", None)
        clinic_id = instance.clinic_id
        if lines_data is not None:
            for line_data in lines_data:
                self._validate_line(line_data, clinic_id)
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            if lines_data is not None:
                instance.lines.all().delete()
                for line_data in lines_data:
                    line = InvoiceLine.objects.create(invoice=instance, **line_data)
                    self._create_dispense_movement_if_needed(
                        invoice=instance,
                        line=line,
                        request_user=self.context["request"].user,
                    )
        return instance
