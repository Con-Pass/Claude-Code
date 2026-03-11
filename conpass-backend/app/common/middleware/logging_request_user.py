import logging

from rest_framework.request import Request as RestFrameworkRequest
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class LoggingRequestUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # /admin/ はDjangoセッション認証を使うためDRFを経由しない
        # （DRFのrequest.userセッターが元のrequestのuserを上書きしてしまうため）
        if request.path.startswith('/admin'):
            response = self.get_response(request)
            return response

        drf_request: RestFrameworkRequest = APIView().initialize_request(request)
        try:
            user = drf_request.user

            if user.is_anonymous:
                logger.info(f"[{request.method}: {request.path}] anonymous user")
            else:
                logger.info(f"[{request.method}: {request.path}] user_id=[{user.id}] user=[{user.username}] "
                            f"account_id=[{user.account.id}] account=[{user.account.name}]")
        except Exception as e:
            logger.info(f"[{request.method}: {request.path}] authenticate error")
            logger.info(e)

        response = self.get_response(request)
        return response
