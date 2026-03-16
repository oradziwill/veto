from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.billing.models import Invoice
from apps.reminders.models import (
    Reminder,
    ReminderEscalationExecution,
    ReminderEscalationRule,
    ReminderEvent,
    ReminderInboundReply,
)
from apps.scheduling.models import Appointment


class Command(BaseCommand):
    help = "Run automated reminder escalation playbooks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clinic-id",
            type=int,
            help="Run only for one clinic.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=200,
            help="Maximum source reminders to evaluate per rule.",
        )

    def handle(self, *args, **options):
        clinic_id = options.get("clinic_id")
        limit = max(1, int(options.get("limit") or 200))
        summary = {"rules": 0, "triggered": 0, "applied": 0, "skipped": 0}

        rules_qs = ReminderEscalationRule.objects.filter(is_active=True).order_by("clinic_id", "id")
        if clinic_id:
            rules_qs = rules_qs.filter(clinic_id=clinic_id)

        for rule in rules_qs.iterator():
            summary["rules"] += 1
            counts = self._run_rule(rule, limit=limit)
            summary["triggered"] += counts["triggered"]
            summary["applied"] += counts["applied"]
            summary["skipped"] += counts["skipped"]

        self.stdout.write(
            self.style.SUCCESS(
                "Reminder escalations complete: "
                f"rules={summary['rules']}, "
                f"triggered={summary['triggered']}, "
                f"applied={summary['applied']}, "
                f"skipped={summary['skipped']}"
            )
        )

    def _run_rule(self, rule: ReminderEscalationRule, *, limit: int) -> dict[str, int]:
        reminders = self._candidate_reminders(rule)[:limit]
        counts = {"triggered": 0, "applied": 0, "skipped": 0}
        for reminder in reminders:
            counts["triggered"] += 1
            status = self._apply_rule(rule, reminder)
            counts[status] += 1
        return counts

    def _candidate_reminders(self, rule: ReminderEscalationRule):
        now = timezone.now()
        cutoff = now - timedelta(minutes=rule.delay_minutes)
        base_qs = Reminder.objects.filter(clinic_id=rule.clinic_id).exclude(
            status=Reminder.Status.CANCELLED
        )

        if rule.trigger_type == ReminderEscalationRule.TriggerType.APPOINTMENT_UNCONFIRMED:
            return (
                base_qs.filter(
                    reminder_type=Reminder.ReminderType.APPOINTMENT,
                    appointment__status=Appointment.Status.SCHEDULED,
                )
                .filter(sent_at__lte=cutoff)
                .exclude(escalation_executions__rule_id=rule.id)
                .order_by("sent_at", "id")
            )

        if rule.trigger_type == ReminderEscalationRule.TriggerType.RESCHEDULE_UNRESOLVED:
            return (
                base_qs.filter(
                    inbound_replies__normalized_intent=ReminderInboundReply.Intent.RESCHEDULE,
                    inbound_replies__action_status=ReminderInboundReply.ActionStatus.NEEDS_REVIEW,
                    inbound_replies__created_at__lte=cutoff,
                )
                .exclude(escalation_executions__rule_id=rule.id)
                .distinct()
                .order_by("id")
            )

        if rule.trigger_type == ReminderEscalationRule.TriggerType.INVOICE_OVERDUE:
            threshold_date = cutoff.date()
            return (
                base_qs.filter(
                    reminder_type=Reminder.ReminderType.INVOICE,
                    invoice__status=Invoice.Status.OVERDUE,
                    invoice__due_date__isnull=False,
                    invoice__due_date__lte=threshold_date,
                )
                .exclude(escalation_executions__rule_id=rule.id)
                .order_by("invoice__due_date", "id")
            )

        return base_qs.none()

    def _apply_rule(self, rule: ReminderEscalationRule, reminder: Reminder) -> str:
        target_key = self._target_key(reminder)
        with transaction.atomic():
            if ReminderEscalationExecution.objects.filter(
                rule_id=rule.id, reminder_id=reminder.id
            ).exists():
                return "skipped"

            applied_count = ReminderEscalationExecution.objects.filter(
                rule_id=rule.id,
                target_key=target_key,
                status=ReminderEscalationExecution.Status.APPLIED,
            ).count()
            if applied_count >= rule.max_executions_per_target:
                ReminderEscalationExecution.objects.create(
                    clinic_id=rule.clinic_id,
                    rule_id=rule.id,
                    reminder_id=reminder.id,
                    target_key=target_key,
                    status=ReminderEscalationExecution.Status.SKIPPED,
                    reason="max_executions_per_target_reached",
                )
                return "skipped"

            applied, reason = self._run_action(rule, reminder)
            ReminderEscalationExecution.objects.create(
                clinic_id=rule.clinic_id,
                rule_id=rule.id,
                reminder_id=reminder.id,
                target_key=target_key,
                status=(
                    ReminderEscalationExecution.Status.APPLIED
                    if applied
                    else ReminderEscalationExecution.Status.SKIPPED
                ),
                reason=reason,
            )
            return "applied" if applied else "skipped"

    def _run_action(self, rule: ReminderEscalationRule, reminder: Reminder) -> tuple[bool, str]:
        if rule.action_type == ReminderEscalationRule.ActionType.ENQUEUE_FOLLOWUP:
            followup = Reminder.objects.create(
                clinic_id=reminder.clinic_id,
                patient_id=reminder.patient_id,
                appointment_id=reminder.appointment_id,
                vaccination_id=reminder.vaccination_id,
                invoice_id=reminder.invoice_id,
                reminder_type=reminder.reminder_type,
                channel=reminder.channel,
                recipient=reminder.recipient,
                subject=f"[Follow-up] {reminder.subject}".strip(),
                body=reminder.body,
                scheduled_for=timezone.now(),
                experiment_key=reminder.experiment_key,
                experiment_variant=reminder.experiment_variant,
            )
            ReminderEvent.objects.create(
                reminder=followup,
                event_type=ReminderEvent.EventType.ENQUEUED,
                payload={
                    "source": "escalation_playbook",
                    "source_reminder_id": reminder.id,
                    "rule_id": rule.id,
                },
            )
            ReminderEvent.objects.create(
                reminder=reminder,
                event_type=ReminderEvent.EventType.ESCALATED,
                payload={"rule_id": rule.id, "followup_reminder_id": followup.id},
            )
            return True, ""

        if rule.action_type == ReminderEscalationRule.ActionType.FLAG_FOR_REVIEW:
            updated = ReminderInboundReply.objects.filter(
                clinic_id=rule.clinic_id,
                reminder_id=reminder.id,
                normalized_intent=ReminderInboundReply.Intent.RESCHEDULE,
                action_status=ReminderInboundReply.ActionStatus.NEEDS_REVIEW,
            ).update(action_note="Escalated by automated playbook.")
            if updated <= 0:
                return False, "no_unresolved_reschedule_reply"
            ReminderEvent.objects.create(
                reminder=reminder,
                event_type=ReminderEvent.EventType.ESCALATED,
                payload={"rule_id": rule.id, "updated_replies": updated},
            )
            return True, ""

        return False, "unsupported_action"

    @staticmethod
    def _target_key(reminder: Reminder) -> str:
        if reminder.appointment_id:
            return f"appointment:{reminder.appointment_id}"
        if reminder.invoice_id:
            return f"invoice:{reminder.invoice_id}"
        if reminder.vaccination_id:
            return f"vaccination:{reminder.vaccination_id}"
        return f"reminder:{reminder.id}"
