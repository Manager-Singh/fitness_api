from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

def flatten_errors(error_data):
    if isinstance(error_data, list):
        return ' '.join([flatten_errors(item) for item in error_data])
    elif isinstance(error_data, dict):
        return ' '.join([flatten_errors(value) for value in error_data.values()])
    else:
        return str(error_data)


def custom_exception_handler(exc, context):
    # First let DRF handle known exceptions
    response = exception_handler(exc, context)

    if response is not None:
        data = response.data

        if isinstance(data, dict) and 'error' in data:
            return Response(data, status=response.status_code)

        flat_error = flatten_errors(data)
        return Response({"success": False, "error": flat_error}, status=response.status_code)

    # 🔥 Handle unexpected exceptions (e.g. ValueError, TypeError)
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return Response({
        "success": False,
        "error": str(exc),
        "type": exc.__class__.__name__
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
