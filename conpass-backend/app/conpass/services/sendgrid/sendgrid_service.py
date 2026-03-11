from logging import getLogger

from django.conf import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

logger = getLogger(__name__)


class SendGrid:

    def send(self, message: Mail):

        try:
            param = {
                'api_key': settings.SENDGRID_API_KEY
            }
            if settings.SENDGRID_DEV_HOST:
                param["host"] = settings.SENDGRID_DEV_HOST
            sg = SendGridAPIClient(**param)
            response = sg.send(message)
        except Exception as e:
            logger.error(e)
            raise e

        logger.info(response)
        return response
