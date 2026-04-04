"""
Portal HTTP API views.

Split across ``views_*.py`` modules; this file re-exports for ``urls.py``.
"""

from .views_auth import (
    PortalAuthConfirmCodeView,
    PortalAuthMagicLinkView,
    PortalAuthRequestCodeView,
)
from .views_booking import (
    PortalAppointmentCancelView,
    PortalAppointmentListCreateView,
    PortalAvailabilityView,
)
from .views_patients import PortalMePatientsView, PortalPatientDetailView
from .views_payments import (
    PortalInvoiceCompleteDepositView,
    PortalInvoiceStripeCheckoutView,
    PortalStripeWebhookView,
)
from .views_public import (
    PortalClinicAvailabilityPublicView,
    PortalClinicPublicView,
    PortalClinicVetsPublicView,
)

__all__ = [
    "PortalAppointmentCancelView",
    "PortalAppointmentListCreateView",
    "PortalAuthConfirmCodeView",
    "PortalAuthMagicLinkView",
    "PortalAuthRequestCodeView",
    "PortalAvailabilityView",
    "PortalClinicAvailabilityPublicView",
    "PortalClinicPublicView",
    "PortalClinicVetsPublicView",
    "PortalInvoiceCompleteDepositView",
    "PortalInvoiceStripeCheckoutView",
    "PortalMePatientsView",
    "PortalPatientDetailView",
    "PortalStripeWebhookView",
]
