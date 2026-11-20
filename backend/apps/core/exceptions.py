"""Consistent error format for the React app: {"detail": "...", "errors": {...}}."""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler


class BusinessRuleError(Exception):
    """Raised by services.py when a business rule fails (e.g. payment exceeds due)."""

    def __init__(self, message, field=None):
        super().__init__(message)
        self.message = message
        self.field = field


def custom_exception_handler(exc, context):
    if isinstance(exc, BusinessRuleError):
        errors = {exc.field: [exc.message]} if exc.field else {}
        return Response({"detail": exc.message, "errors": errors}, status=status.HTTP_400_BAD_REQUEST)

    if isinstance(exc, DjangoValidationError):
        exc = ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)

    response = exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    if isinstance(data, dict) and "detail" in data and len(data) == 1:
        response.data = {"detail": str(data["detail"]), "errors": {}}
    else:
        response.data = {"detail": "Please correct the errors below.", "errors": data}
    return response
