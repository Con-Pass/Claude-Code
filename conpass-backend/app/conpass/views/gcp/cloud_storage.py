import base64
import os
import traceback
from logging import getLogger

import google.auth

from conpass.models import File, Contract
from conpass.services.contract.contract_service import ContractService
from conpass.services.gcp.cloud_storage import GoogleCloudStorage, GCSBucketName
from conpass.views.gcp.serializer.cloud_storage_serializer import GoogleCloudStorageUploadBlobSerializer, \
    GoogleCloudStorageUploadSerializer, GoogleCloudStorageDownloadSerializer, GoogleCloudStorageResponseBodySerializer, \
    GoogleCloudStorageDeleteFilesSerializer, GoogleCloudStorageDeleteLinkedFileSerializer
from conpass.services.directory.directory_service import DirectoryService
from conpass.models.constants import Statusable

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
import datetime
from django.utils.timezone import make_aware
from django.conf import settings

logger = getLogger(__name__)


class GoogleCloudStorageUpload(APIView, GoogleCloudStorage):

    def get(self, request):
        """
        GCSにファイルをアップロードする
        アップロードするときはconpass_fileを更新する
        一度サーバ側でテンポラリに保存したファイルをGCSにアップロードするような場合に使う
        （基本的には使われないと思います）
        """
        req_serializer = GoogleCloudStorageUploadSerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data

        filename = data.get("filename")
        path = data.get("path")
        description = data.get("description")
        datatype = data.get("datatype")
        fileid = data.get("fileid")
        userid = self.request.user.id

        try:
            self.set_user_id(userid)
            size = os.path.getsize(path + filename)
            client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
            file = self.prepare_file_record(fileid, filename, datatype)
            _, gcs_path = self.get_gcs_fileinfo(file)
            gcs_blob = bucket.blob(gcs_path)  # GCS側
            gcs_blob.upload_from_filename(path + filename)  # local側
            self.set_file_info(file=file, filename=filename, url=gcs_path, datatype=datatype, description=description,
                               size=size)
            res = GoogleCloudStorageResponseBodySerializer(file)
            return Response(data=res.data)
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"message": "GCSへのアップロードに失敗しました"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            self.set_user_id(0)  # クリアしておく


class GoogleCloudStorageUploadBlob(APIView, GoogleCloudStorage):

    def post(self, request):
        """
        GCSにBlobをアップロードする
        ブラウザから直接UPする時はこちらを使います
        アップロードするときはconpass_fileを更新する
        """
        req_serializer = GoogleCloudStorageUploadBlobSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data

        filename = data.get("filename")
        blob = data.get("blob")
        description = data.get("description")
        datatype = data.get("datatype")
        fileid = data.get("fileid")
        userid = self.request.user.id

        try:
            self.set_user_id(userid)
            client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
            file = self.prepare_file_record(fileid, filename, datatype)
            _, gcs_path = self.get_gcs_fileinfo(file)
            gcs_blob = bucket.blob(gcs_path)  # GCS側
            gcs_blob.upload_from_file(blob)  # local側
            self.set_file_info(file=file, filename=filename, url=gcs_path, datatype=datatype, description=description,
                               size=blob.size)
            res = GoogleCloudStorageResponseBodySerializer(file)
            return Response(data=res.data)
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"message": "GCSへのアップロードに失敗しました"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            self.set_user_id(0)  # クリアしておく


class GoogleCloudStorageDownload(APIView, GoogleCloudStorage):

    def get(self, request):
        """
        GCSからファイルをダウンロードする
        base64した形で応答するので、ファイルに保存するなりダウンロードさせるなり処理してください
        """
        req_serializer = GoogleCloudStorageDownloadSerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data
        file_id = data.get("fileid")
        user_id = self.request.user.id
        try:
            self.set_user_id(user_id)
            file = self.get_file_from_id(file_id)
            filename, fileurl = file.name, file.url
            if not filename or not fileurl:
                raise Exception("ファイルが見つかりません")
            client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
            blob = bucket.blob(fileurl)  # GCS側
            str_buffer = blob.download_as_bytes()
            b64 = base64.b64encode(str_buffer).decode("utf-8")
            response = {
                "name": filename,
                "url": fileurl,
                "base64data": b64,
            }
            return Response(response, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"message": "GCSからのダウンロードに失敗しました"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            self.set_user_id(0)  # クリアしておく


class GoogleCloudStoragePreview(APIView, GoogleCloudStorage):

    def get(self, request):
        """
        GCSから署名付きURLを生成する
        """
        req_serializer = GoogleCloudStorageDownloadSerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data
        file_id = data.get("fileid")
        user_id = self.request.user.id
        disposition = data.get("disposition")
        # dispositionが指定されていないもしくはinlineでもattachmentでもない場合はinlineをデフォルトにする
        if not disposition or disposition not in ["inline", "attachment"]:
            disposition = "inline"
        try:
            self.set_user_id(user_id)
            file = self.get_file_from_id(file_id)

            # 権限チェック
            contract = file.contract_files.first()
            service = ContractService()
            res = service.check_contract_permission(self.request.user, contract)
            if res["status"] == status.HTTP_400_BAD_REQUEST:
                return Response({"message": res["message"]}, status=res["status"])

            filename, fileurl = file.name, file.url
            if not filename or not fileurl:
                raise Exception("ファイルが見つかりません")

            file_extension = os.path.splitext(filename)[1]  # ファイル名から拡張子を取得
            content_type = self.get_content_type(file_extension)
            if not content_type:
                content_type = 'application/octet-stream'  # 拡張子に対応するMIMEタイプが見つからない場合のデフォルト値
            url = self.generate_download_signed_url_v4(fileurl, content_type, disposition, filename)  # 署名付きURLを生成するメソッドを呼び出す
            response = {
                "name": filename,
                "url": fileurl,
                "signed_url": url,
            }
            return Response(response, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"message": "署名付きURLの生成に失敗しました"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            self.set_user_id(0)  # クリアしておく

    def get_content_type(self, file_extension):
        """
        ファイル拡張子に基づいてMIMEタイプを取得する
        """
        if file_extension == ".pdf":
            return "application/pdf"
        elif file_extension == ".txt":
            return "text/plain"
        elif file_extension == ".csv":
            return "text/csv"
        elif file_extension == ".json":
            return "application/json"
        elif file_extension == ".xls":
            return "application/vnd.ms-excel"
        elif file_extension == ".xlsx":
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif file_extension == ".ppt":
            return "application/vnd.ms-powerpoint"
        elif file_extension == ".pptx":
            return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        elif file_extension == ".doc":
            return "application/msword"
        elif file_extension == ".docx":
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif file_extension == ".png":
            return "image/png"
        elif file_extension == ".jpg" or file_extension == ".jpeg":
            return "image/jpeg"
        else:
            return None

    def generate_download_signed_url_v4(self, fileurl, content_type, disposition, filename):
        """
        Generates a v4 signed URL for downloading a blob.
        """

        has_credentials = settings.GOOGLE_APPLICATION_CREDENTIALS

        if has_credentials:
            client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
            blob = bucket.blob(fileurl)  # GCS側
            url = blob.generate_signed_url(
                version="v4",
                # This URL is valid for 10 minutes
                expiration=datetime.timedelta(minutes=10),
                # Allow GET requests using this URL.
                method="GET",
                query_parameters={
                    'response-content-type': content_type,  # レスポンスのコンテンツタイプを指定する
                    'response-content-disposition': f'{disposition}; filename="{filename}"'  # レスポンスのダウンロードファイル名を指定する
                }
            )
            logger.warning(url)
            return url
        else:
            credentials, project_id = google.auth.default()
            credentials.refresh(google.auth.transport.requests.Request())

            logger.warning(credentials.token)
            logger.warning(credentials.service_account_email)

            client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
            blob = bucket.blob(fileurl)  # GCS側
            url = blob.generate_signed_url(
                version="v4",
                # This URL is valid for 10 minutes
                expiration=datetime.timedelta(minutes=10),
                access_token=credentials.token,
                service_account_email=credentials.service_account_email,
                # Allow GET requests using this URL.
                method="GET",
                query_parameters={
                    'response-content-type': content_type,  # レスポンスのコンテンツタイプを指定する
                    'response-content-disposition': f'{disposition}; filename="{filename}"'  # レスポンスのダウンロードファイル名を指定する
                }
            )
            logger.warning(url)
            return url


class GoogleCloudStorageFileInfo(APIView, GoogleCloudStorage):

    def get(self, request):
        """
        GCSにあるファイルオブジェクトの情報を得る
        現状、ファイル名しか取れません…
        """
        req_serializer = GoogleCloudStorageDownloadSerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data
        file_id = data.get("fileid")
        user_id = self.request.user.id
        try:
            self.set_user_id(user_id)
            file = self.get_file_from_id(file_id)
            fileurl = file.url
            client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
            blob = bucket.blob(fileurl)  # GCS側
            response = {
                "name": blob.name,
                "size": blob.size,
                "content_type": blob.content_type,
            }
            return Response(response, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"message": "ファイル情報の取得に失敗しました"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            self.set_user_id(0)  # クリアしておく


class GoogleCloudStorageFileList(APIView, GoogleCloudStorage):

    def get(self, request):
        """
        GCSの指定の階層にあるファイル一覧を得る
        DBではなく、GCSのファイル情報を取得するため、通常は使わない
        """
        try:
            client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
            files = []
            for file in client.list_blobs(bucket.name):
                files.append(file.name)
            return Response(files, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"message": "ファイル情報の取得に失敗しました"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            self.set_user_id(0)  # クリアしておく


class GoogleCloudStorageDeleteFiles(APIView, GoogleCloudStorage):

    def post(self, request):
        """
        GCSのファイル（複数）を削除する
        file id指定で、GCS上のファイル削除と同時にfile情報もDISABLEにする
        """
        req_serializer = GoogleCloudStorageDeleteFilesSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data
        fileids = data.get("ids")
        userid = self.request.user.id
        removed_ids = []
        try:
            for fileid in fileids:
                self.set_user_id(userid)
                client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
                file = self.get_file_from_id(fileid)
                gcs_blob = bucket.blob(file.url)  # GCS側
                gcs_blob.delete()
                # file の status を無効に
                file.status = File.Status.DISABLE.value
                file.updated_by_id = userid
                file.updated_at = make_aware(datetime.datetime.now())
                file.save()
                removed_ids.append(fileid)
            return Response(removed_ids)
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"message": "GCSのファイル削除に失敗しました"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            self.set_user_id(0)  # クリアしておく


class GoogleCloudStorageFileLinkedContractDeleteView(APIView, GoogleCloudStorage):
    """
    契約書に紐付けされたファイルを削除する
    app/conpass/views/file/views.pyのFileLinkedContractDeleteViewに論理削除バージョンあり
    """
    def post(self, request):
        req_serializer = GoogleCloudStorageDeleteLinkedFileSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        contract_id = req_serializer.data.get('id')
        file_id = req_serializer.data.get('fileId')
        user = self.request.user
        now = make_aware(datetime.datetime.now())

        # 契約書の取得
        wheres = {
            'pk': contract_id,
            'account': user.account
        }
        excludes = {
            'status': Contract.Status.DISABLE.value
        }
        try:
            contract = Contract.objects.filter(**wheres).exclude(**excludes).select_related('directory').prefetch_related('file').get()
        except Contract.DoesNotExist as e:
            logger.info(e)
            return Response("契約書が見つかりません。", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
            return Response("エラーが発生しました。", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            directory_service = DirectoryService()
            visible_directories = directory_service.get_allowed_directories(user, contract.type)
            if contract.directory in visible_directories:
                # 削除するファイルの検索
                file = None
                for f in contract.file.all():
                    if f.id == file_id and f.status == Statusable.Status.ENABLE.value and f.type == File.Type.ETC.value and f.account_id == user.account_id:
                        file = f
                        break
                if file is not None:
                    # GCS上のファイルを削除
                    self.set_user_id(user.id)
                    client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
                    gcs_blob = bucket.blob(file.url)  # GCS側
                    gcs_blob.delete()
                    # ファイルを論理削除
                    file.status = Statusable.Status.DISABLE.value
                    file.updated_at = now
                    file.updated_by_id = user.id
                    file.save()
                else:
                    return Response("該当のファイルが見つかりません。", status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response("契約書の閲覧権限がありません。", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response("該当のファイルの削除に失敗しました。", status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            self.set_user_id(0)  # クリアしておく

        return Response("該当のファイルを削除しました。", status=status.HTTP_200_OK)
