import traceback
import zipfile

from django.conf import settings
from logging import getLogger
from rest_framework import status
from rest_framework.response import Response

from conpass.services.gcp.cloud_storage import GoogleCloudStorage, GCSBucketName
from conpass.views.sys.common import SysAPIView
from conpass.views.sys.upload.serializer.upload_serializer import SysUploadLoginAdFileRequestSerializer

logger = getLogger(__name__)


class SysUploadLoginAdFileView(SysAPIView, GoogleCloudStorage):

    def post(self, request):
        """
        アップロード画面でログイン広告用ファイルをアップロードする
        GCSにファイルをアップロード
        """
        req_serializer = SysUploadLoginAdFileRequestSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data
        file = data.get("file")

        if not zipfile.is_zipfile(file):
            return Response({"message": "zipファイル以外はアップロード出来ません。"}, status=status.HTTP_400_BAD_REQUEST)

        with zipfile.ZipFile(file) as zf:
            has_index_file = False
            for filename in zf.namelist():
                if "index.html" in filename:
                    has_index_file = True
                    """
                    example (2).zip のようなファイルが送信されてきたときに filename では、example/index.html となる為
                    zipファイル名から取らずにここで取得する。
                    """
                    if '/' in filename:
                        top_dir_name_offset = len(filename.split('/', 1)[0]) + 1
                    else:
                        top_dir_name_offset = 0
                    break
            if not has_index_file:
                return Response({"message": "index.htmlが含まれていません。"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                client, bucket = self.get_cloudstorage(GCSBucketName.WEB)

                current_blobs = bucket.list_blobs(prefix=settings.GCS_LOGIN_AD_PREFIX)
                for blob in current_blobs:
                    logger.info(blob)
                    blob.delete()

                for fileinfo in filter(lambda i: not i.is_dir(), zf.infolist()):
                    gcs_path = settings.GCS_LOGIN_AD_PREFIX + fileinfo.filename[top_dir_name_offset:]
                    gcs_blob = bucket.blob(gcs_path)
                    content_type = self._get_content_type(fileinfo.filename)
                    with zf.open(fileinfo, "r") as f:
                        gcs_blob.upload_from_file(file_obj=f, content_type=content_type)
                    gcs_blob.cache_control = "no-cache"
                    gcs_blob.patch()

            except Exception as e:
                logger.error(f"{e}: {traceback.format_exc()}")
                return Response({"message": "GCSへのアップロードに失敗しました"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response("ログイン広告のアップロードが完了しました。", status=status.HTTP_200_OK)

    def _get_content_type(self, filename):
        mimes = {
            "text/html": ["html", "htm"],
            "text/css": ["css"],
            "text/javascript": ["js"],
            "image/png": ["png"],
            "image/gif": ["gif"],
            "image/jpeg": ["jpg", "jpeg", "jfif", "pjpeg", "pjp"],
            "image/svg": ["svg"],
            "image/webp": ["webp"],
        }
        ext_pos = filename.rfind('.')
        if ext_pos > 0:
            ext = filename[ext_pos + 1:]
        else:
            return None
        for k, v in mimes.items():
            if ext in v:
                return k
        return None
