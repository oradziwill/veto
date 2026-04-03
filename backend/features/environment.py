"""
Behave hooks for Django (behave-django).

Use ``python manage.py behave --simple`` for API tests (no live server).
"""


def django_ready(context):
    """Runs inside each scenario's DB transaction."""
    from rest_framework.test import APIClient

    context.api = APIClient()
    context.last_response = None
    context.clinic = None
    context.doctor = None
    context.receptionist = None
