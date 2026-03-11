from logging import getLogger
from typing import Union

from django.http import HttpRequest
from rest_framework.request import Request
from rest_framework.response import Response

logger = getLogger(__name__)


def log_internal_api(view):
    def wrapper(self, request: Union[Request, HttpRequest], *args, **kwargs):
        logger.info("Internal API Request", extra={
            'path': request.get_full_path(),
            'headers': request.headers,
            'query': request.POST,
        })
        response: Response = view(self, request)
        logger.info("Internal API Response", extra={
            'status_code': response.status_code,
            'headers': response.headers,
            'data': response.data,
        })
        return response

    return wrapper
