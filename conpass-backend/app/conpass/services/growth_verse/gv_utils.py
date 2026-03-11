import datetime
import google.auth
from google.cloud import storage
from django.conf import settings
from logging import getLogger

logger = getLogger(__name__)


class GvUtils():
    @classmethod
    def generate_signed_url_v4(cls, fileurl):
        """
        Generates a v4 signed URL for downloading a blob.
        """

        has_credentials = settings.GOOGLE_APPLICATION_CREDENTIALS

        if has_credentials:
            project_id = "purple-conpass"
            client = storage.Client(project_id)
            bucket = client.bucket(settings.GCS_BUCKET_NAME_FILE)
            blob = bucket.blob(fileurl)  # GCS側
            url = blob.generate_signed_url(
                version="v4",
                # This URL is valid for 10 minutes
                expiration=datetime.timedelta(minutes=10),
                # Allow GET requests using this URL.
                method="GET",
            )
            logger.info(url)
            return url
        else:
            credentials, project_id = google.auth.default()
            credentials.refresh(google.auth.transport.requests.Request())

            logger.info(credentials.token)
            logger.info(credentials.service_account_email)

            client = storage.Client(project_id)
            bucket = client.bucket(settings.GCS_BUCKET_NAME_FILE)
            blob = bucket.blob(fileurl)  # GCS側
            url = blob.generate_signed_url(
                version="v4",
                # This URL is valid for 10 minutes
                expiration=datetime.timedelta(minutes=10),
                access_token=credentials.token,
                service_account_email=credentials.service_account_email,
                # Allow GET requests using this URL.
                method="GET",
            )
            logger.info(url)
            return url
