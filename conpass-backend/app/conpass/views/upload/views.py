import datetime
import os
import traceback
import zipfile
import json
import tempfile
from logging import getLogger

import google.auth

from celery.result import AsyncResult
from django.utils.timezone import make_aware
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.models import Contract, File, FileUploadStatus
from conpass.models.constants import ContractTypeable
from conpass.services.contract.contract_upload_prediction_task import prediction_on_upload_task, zip_upload_task, \
    is_contract_exist
from conpass.services.gcp.cloud_storage import GoogleCloudStorage, GCSBucketName
from conpass.services.gcp.prediction import PredictionRequestFile
from conpass.views.upload.serializer.upload_serializer import UploadContractFileRequestSerializer, \
    UploadFileLinkedContractRequestSerializer, UploadContractUrlRequestSerializer, NotifyUploadedToGcsRequestSerializer

from pdf2image import convert_from_path
from pdf2image.exceptions import PDFPageCountError
from pyzbar.pyzbar import decode, ZBarSymbol

logger = getLogger(__name__)


class UploadContractFileView(APIView, GoogleCloudStorage):

    def post(self, request):
        """
        アップロード画面で契約書テンプレートもしくは過去契約書をアップロードする
        GCSにファイルをアップロード
        Fileデータが作られる
        Contractデータを作成し、FileとManyToManyで紐付け
        Predictでメタ情報デフォルト項目を取得し、MetaData に保存し、MetaData->ContractとContractBody->Contractに紐付け
        """
        req_serializer = UploadContractFileRequestSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data

        filename = data.get("filename")
        blob = data.get("blob")
        description = data.get("description")
        datatype = data.get("datatype")
        conpass_contract_type = data.get("conpassContractType")
        is_open = data.get("isOpen")
        user = self.request.user

        if datatype == File.Type.BULK.value:
            _, ext = os.path.splitext(filename)
            if ext != ".zip":
                return Response("zipファイル以外は使用できません。", status=status.HTTP_400_BAD_REQUEST)

            self.set_user_id(user.id)
            now = make_aware(datetime.datetime.now())
            client, bucket = self.get_cloudstorage(GCSBucketName.API)
            gcs_path = settings.GCS_FILE_PREFIX + "/bulk/" + str(user.id) + "/" + now.strftime("%Y%m%d%H%M%S") + "/" + filename
            gcs_blob = bucket.blob(gcs_path)  # GCS側
            gcs_blob.upload_from_file(blob)  # local側

            task_id: AsyncResult = zip_upload_task.delay(
                zip_file_path=gcs_path,
                bucket_type='api',
                user_id=user.id,
                is_open=is_open,
                conpass_contract_type=conpass_contract_type,
                directory_id=data.get("directoryId"),
                is_provider=data.get("isProvider"),
                description=description,
                is_meta_check=data.get('isMetaCheck') == 1,
                renew_notify=data.get('renewNotify'),
                upload_id=None,
            )
            logger.info(f"Pushed zip upload task: {task_id}")

            return Response(filename + "を処理キューに登録しました。", status=status.HTTP_200_OK)

        elif datatype == File.Type.CONTRACT_QR.value:
            # QRコード付きファイルアップロード
            qr_array = []  # QRコードから取得したデータを格納する
            error_message = "QRコードが読み取れませんでした。PDF内にQRコードが存在しない、または識別ができませんでした。"  # エラーメッセージ
            is_qr_code = False
            _, file_ext = os.path.splitext(blob.temporary_file_path())
            if file_ext.lower() == ".pdf":
                try:
                    pages = convert_from_path(blob.temporary_file_path())
                except PDFPageCountError:
                    return Response({"message": error_message}, status=status.HTTP_400_BAD_REQUEST)
                for page in reversed(pages):  # Footer にQRコードがあるので逆順で読み取る
                    if is_qr_code:
                        break
                    decoded_qr = decode(page, symbols=[ZBarSymbol.QRCODE])
                    if decoded_qr:
                        for qr in decoded_qr:
                            qr_data = qr.data.decode("utf-8")
                            try:
                                qr_array = json.loads(qr_data)
                            except ValueError:
                                error_message = "QRコード内のデータ形式がConPassのデータ形式と異なります。"
                                continue  # QRコードのデータがJSON形式ではない場合はスキップ
                            if not isinstance(qr_array, dict):
                                error_message = "QRコード内のデータ形式がConPassのデータ形式と異なります。"
                                continue  # QRコードのデータが辞書型ではない場合はスキップ
                            if "id" in qr_array:
                                # QRコードを読み取り取得したデータから紐付ける Contract を抽出する
                                wheres = {
                                    'id': qr_array["id"],
                                    'account': user.account
                                }
                                contract = is_contract_exist(wheres=wheres)
                                if contract:
                                    datatype = File.Type.CONTRACT_QR.value
                                    is_qr_code = True
                                    break
                                else:
                                    error_message = "契約書が見つかりませんでした。該当の契約書データが存在しない、" \
                                                    "または、該当の契約書データが削除がされています。"
                            else:
                                error_message = "QRコード内のデータ形式がConPassのデータ形式と異なります。"

                # アップロードデータを紐づける
                if is_qr_code:
                    try:
                        self.set_user_id(user.id)
                        client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
                        file = self.prepare_file_record(0, filename, datatype)
                        _, gcs_path = self.get_gcs_fileinfo(file)
                        gcs_blob = bucket.blob(gcs_path)  # GCS側
                        gcs_blob.upload_from_file(blob)  # local側
                        self.set_file_info(file=file, filename=filename, url=gcs_path, datatype=datatype,
                                           description=description, size=blob.size)
                    except Exception as e:
                        logger.error(f"{e}: {traceback.format_exc()}")
                        return Response({"message": "GCSへのアップロードに失敗しました。"},
                                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    finally:
                        self.set_user_id(0)  # クリアしておく
                    contract.file.add(file)  # 契約書にファイルを紐付ける（save不要）
                else:
                    return Response({"message": error_message}, status=status.HTTP_400_BAD_REQUEST)

            return Response(
                {"message": "契約書ID:" + str(qr_array["id"]) + " に紐付けされました。"},
                status=status.HTTP_200_OK
            )

        else:
            # ファイルアップロード
            try:
                file_size = os.path.getsize(blob.temporary_file_path())
                logger.info(f"upload file size: {file_size}")
                if file_size >= int(settings.UPLOAD_PDF_FILE_SIZE_MAX):
                    max_size_mb = int(int(settings.UPLOAD_PDF_FILE_SIZE_MAX) / 1024 / 1024)
                    return Response(
                        {"message": f"{max_size_mb}MB以上のPDFファイルはメタ情報を抽出できないためアップロードできません。"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                self.set_user_id(user.id)
                client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
                file = self.prepare_file_record(0, filename, datatype)
                _, gcs_path = self.get_gcs_fileinfo(file)
                gcs_blob = bucket.blob(gcs_path)  # GCS側
                gcs_blob.upload_from_file(blob)  # local側
                self.set_file_info(file=file, filename=filename, url=gcs_path, datatype=datatype, description=description,
                                   size=blob.size)
            except Exception as e:
                logger.error(f"{e}: {traceback.format_exc()}")
                return Response({"message": "GCSへのアップロードに失敗しました。"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                self.set_user_id(0)  # クリアしておく

            # Contract を作る
            contract = self.create_contract(file, user, data)
            contract.file.add(file)  # Many to Many はIDが確定してから

            # Predict でメタ情報と本文を取得
            predict_file = PredictionRequestFile(
                id=file.id,
                url=file.url,
            )
            task_id: AsyncResult = prediction_on_upload_task.delay(
                predict_file_dict=predict_file.to_dict(),
                contract_id=contract.id,
                user_id=user.id,
                datatype=datatype,
                conpass_contract_type=conpass_contract_type,
                is_meta_check=data.get('isMetaCheck') == 1,
                renew_notify=data.get('renewNotify'),
                upload_id=None,
            )
            logger.info(f"Pushed contract prediction task: {task_id}")

            return Response(file.name + "の登録が完了しました。", status=status.HTTP_200_OK)

    def create_contract(self, file, user, data):
        now = make_aware(datetime.datetime.now())
        contract = Contract()
        contract.name = file.name
        status = Contract.Status.ENABLE.value
        type = file.type
        if type == ContractTypeable.ContractType.PAST.value:
            status = Contract.Status.SIGNED_BY_PAPER.value
            type = ContractTypeable.ContractType.CONTRACT.value
        elif type == ContractTypeable.ContractType.TEMPLATE.value:
            status = Contract.Status.UNUSED.value
        contract.type = type
        contract.account = user.account
        # contract.client =
        contract.directory_id = data.get('directoryId')
        contract.is_provider = True\
            if data.get('isProvider') and type == ContractTypeable.ContractType.TEMPLATE.value else False
        contract.is_open = True
        contract.status = status
        contract.created_at = now
        contract.created_by = user
        contract.updated_at = now
        contract.updated_by = user
        contract.save()
        if contract.type == ContractTypeable.ContractType.TEMPLATE.value:
            contract.template_id = contract.id  # 自分自身
        contract.origin_id = contract.id  # 自分自身
        contract.save()
        return contract


class UploadFileLinkedContractView(APIView, GoogleCloudStorage):

    def post(self, request):
        """
        契約書に紐付ける任意のファイルをアップロードする
        GCSにファイルをアップロード
        Fileデータが作られる
        ContractとFileをManyToManyで紐付け
        """
        req_serializer = UploadFileLinkedContractRequestSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data

        filename = data.get("filename")
        blob = data.get("blob")
        description = data.get("description")
        contractId = int(data.get("contractId"))
        user = self.request.user
        datatype = File.Type.ETC.value

        # 紐付ける Contract を抽出しておく
        wheres = {
            'id': contractId,
            'account': user.account
        }
        try:
            contract = Contract.objects.exclude(status=Contract.Status.DISABLE.value).filter(**wheres).get()
        except Contract.DoesNotExist as e:
            logger.info(e)
            return Response("契約書が見つかりません", status=status.HTTP_400_BAD_REQUEST)

        # ファイルアップロード
        try:
            self.set_user_id(user.id)
            client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
            file = self.prepare_file_record(0, filename, datatype)
            _, gcs_path = self.get_gcs_fileinfo(file)
            gcs_blob = bucket.blob(gcs_path)  # GCS側
            gcs_blob.upload_from_file(blob)  # local側
            self.set_file_info(file=file, filename=filename, url=gcs_path, datatype=datatype, description=description,
                               size=blob.size)
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"message": "GCSへのアップロードに失敗しました"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            self.set_user_id(0)  # クリアしておく

        # 契約書にファイルを紐付ける（save不要）
        contract.file.add(file)

        return Response(file.name + "の登録が完了しました。", status=status.HTTP_200_OK)


class UploadContractUrlView(APIView, GoogleCloudStorage):

    def post(self, request):
        """
        アップロード画面で契約書テンプレートもしくは過去契約書をアップロードするための
        アップロード先のGCSの署名付きURLを取得。
        取得したURLを使用してGCSへのファイルアップロードはクライアント側で実行する。

        GCSアップロード後に、Cloud Functions経由で下記の処理を実行するために必要情報をDBに格納しておく。
        ・Fileデータ作成
        ・Contractデータを作成し、FileとManyToManyで紐付け
        ・Predictでメタ情報デフォルト項目を取得し、MetaData に保存し、MetaData->ContractとContractBody->Contractに紐付け
        """
        req_serializer = UploadContractUrlRequestSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data

        filename = data.get("filename")
        description = data.get("description")
        datatype = data.get("datatype")
        directory_id = data.get("directoryId")
        conpass_contract_type = data.get("conpassContractType")
        renew_notify = data.get('renewNotify')
        is_provider = data.get("isProvider")
        is_meta_check = data.get('isMetaCheck')
        is_open = data.get("isOpen")
        user = self.request.user

        self.set_user_id(user.id)
        fileuploadstatus = self.prepare_file_upload_status_record(0, filename, datatype)
        _, gcs_path = self.get_gcs_fileinfo2(fileuploadstatus, datatype == FileUploadStatus.Type.BULK.value)
        file_path = '' if datatype == FileUploadStatus.Type.BULK.value else gcs_path
        zip_path = gcs_path if datatype == FileUploadStatus.Type.BULK.value else ''
        self.set_file_upload_status_info(
            fileuploadstatus=fileuploadstatus,
            filename=filename,
            description=description,
            datatype=datatype,
            file_path=file_path,
            zip_path=zip_path,
            directory_id=directory_id,
            contract_type=conpass_contract_type,
            renew_notify=renew_notify,
            is_provider=is_provider,
            is_meta_check=is_meta_check,
            is_open=is_open)

        path = file_path or zip_path
        save_name = os.path.basename(path)
        signed_url = self.generate_upload_signed_url_v4(gcs_path)
        response = {
            "uploadUrl": signed_url,
            "id": save_name.rsplit('.', 1)[0],
            "filePath": file_path,
            "zipPath": zip_path
        }
        self.set_file_upload_status_upload_status(fileuploadstatus=fileuploadstatus, upload_status=FileUploadStatus.UploadStatus.REQUEST.value)
        return Response(response, status=status.HTTP_200_OK)

    def generate_upload_signed_url_v4(self, url):
        """
        アップロード用の署名付きURLを生成する
        """
        has_credentials = settings.GOOGLE_APPLICATION_CREDENTIALS

        client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
        blob = bucket.blob(url)
        if has_credentials:
            url = blob.generate_signed_url(
                version="v4",
                # This URL is valid for 3 minutes
                expiration=datetime.timedelta(minutes=3),
                method="PUT"
            )
        else:
            credentials, project_id = google.auth.default()
            credentials.refresh(google.auth.transport.requests.Request())
            url = blob.generate_signed_url(
                version="v4",
                # This URL is valid for 3 minutes
                expiration=datetime.timedelta(minutes=3),
                access_token=credentials.token,
                service_account_email=credentials.service_account_email,
                method="PUT"
            )
        return url


class NotifyUploadedToGcsView(APIView, GoogleCloudStorage):

    def post(self, request):
        """
        GCSにアップロードされたことの通知を受け取る
        Fileデータが作られる
        Contractデータを作成し、FileとManyToManyで紐付け
        Predictでメタ情報デフォルト項目を取得し、MetaData に保存し、MetaData->ContractとContractBody->Contractに紐付け
        """
        req_serializer = NotifyUploadedToGcsRequestSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data

        id = data.get("id")
        filePath = data.get("filePath")
        zipPath = data.get("zipPath")
        size = data.get('size')

        logger.info(f"id: {id}")
        logger.info(f"filePath: {filePath}")
        logger.info(f"zipPath: {zipPath}")
        logger.info(f"size: {size}")

        try:
            uploadStatus = FileUploadStatus.objects.get(id=id)
        except FileUploadStatus.DoesNotExist as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["アプロードステータス情報が見つかりません"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # ステータスを「GCSに格納された」に更新
        self.set_file_upload_status_upload_status(fileuploadstatus=uploadStatus, upload_status=FileUploadStatus.UploadStatus.STORED.value)
        self.set_file_upload_status_size(fileuploadstatus=uploadStatus, size=size)

        client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
        gcs_blob = bucket.blob(filePath)  # GCSにアップロードされたファイル

        if uploadStatus.type == FileUploadStatus.Type.BULK.value:
            filename = uploadStatus.name
            _, ext = os.path.splitext(filename)
            if ext != ".zip":
                self.set_file_upload_status_error_message(fileuploadstatus=uploadStatus, error_message="zipファイル以外は使用できません。")
                return Response("zipファイル以外は使用できません。", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # 非同期処理でzipファイルを解析
            task_id: AsyncResult = zip_upload_task.delay(
                zip_file_path=uploadStatus.zip_path,
                bucket_type='file',
                user_id=uploadStatus.user.id,
                is_open=uploadStatus.is_open,
                conpass_contract_type=uploadStatus.contract_type,
                directory_id=uploadStatus.directory.id,
                is_provider=uploadStatus.is_provider,
                description=uploadStatus.description,
                is_meta_check=uploadStatus.is_meta_check == 1,
                renew_notify=uploadStatus.renew_notify,
                upload_id=uploadStatus.upload_id,
            )
            logger.info(f"Pushed zip upload task: {task_id}")
            self.set_file_upload_status_task_id(fileuploadstatus=uploadStatus, task_id=task_id)
            return Response(filename + "を処理キューに登録しました。", status=status.HTTP_200_OK)

        elif uploadStatus.type == FileUploadStatus.Type.CONTRACT_QR.value:
            # QRコード付きファイルアップロード
            qr_array = []  # QRコードから取得したデータを格納する
            error_message = "QRコードが読み取れませんでした。PDF内にQRコードが存在しない、または識別ができませんでした。"  # エラーメッセージ
            is_qr_code = False

            # 一時ファイルを作成
            content = gcs_blob.download_as_string()
            with tempfile.NamedTemporaryFile(delete=True) as temp_file:
                # 一時ファイルにデータを書き込み
                temp_file.write(content)

                _, file_ext = os.path.splitext(filePath)
                if file_ext.lower() == ".pdf":
                    try:
                        pages = convert_from_path(temp_file.name)
                    except PDFPageCountError:
                        self.set_file_upload_status_error_message(fileuploadstatus=uploadStatus, error_message=error_message)
                        return Response({"message": error_message}, status=status.HTTP_400_BAD_REQUEST)
                    datatype = uploadStatus.type
                    for page in reversed(pages):  # Footer にQRコードがあるので逆順で読み取る
                        if is_qr_code:
                            break
                        decoded_qr = decode(page, symbols=[ZBarSymbol.QRCODE])
                        if decoded_qr:
                            for qr in decoded_qr:
                                qr_data = qr.data.decode("utf-8")
                                try:
                                    qr_array = json.loads(qr_data)
                                except ValueError:
                                    error_message = "QRコード内のデータ形式がConPassのデータ形式と異なります。"
                                    continue  # QRコードのデータがJSON形式ではない場合はスキップ
                                if not isinstance(qr_array, dict):
                                    error_message = "QRコード内のデータ形式がConPassのデータ形式と異なります。"
                                    continue  # QRコードのデータが辞書型ではない場合はスキップ
                                if "id" in qr_array:
                                    # QRコードを読み取り取得したデータから紐付ける Contract を抽出する
                                    wheres = {
                                        'id': qr_array["id"],
                                        'account': uploadStatus.account
                                    }
                                    contract = is_contract_exist(wheres=wheres)
                                    if contract:
                                        datatype = File.Type.CONTRACT_QR.value
                                        is_qr_code = True
                                        break
                                    else:
                                        error_message = "契約書が見つかりませんでした。該当の契約書データが存在しない、" \
                                                        "または、該当の契約書データが削除がされています。"
                                else:
                                    error_message = "QRコード内のデータ形式がConPassのデータ形式と異なります。"

                    # アップロードデータを紐づける
                    if is_qr_code:
                        try:
                            self.set_user_id(uploadStatus.user.id)
                            client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
                            file = self.prepare_file_record(0, uploadStatus.name, uploadStatus.type)
                            # アップロード履歴とファイル情報を紐づける
                            self.set_file_upload_status_file(fileuploadstatus=uploadStatus, file_id=file.id)
                            _, gcs_path = self.get_gcs_fileinfo(file)
                            new_gcs_blob = bucket.blob(gcs_path)  # GCS側

                            # 一時ファイルをGCS Blobにアップロード
                            with open(temp_file.name, 'rb') as source_file:
                                new_gcs_blob.upload_from_file(source_file)  # local側
                            # 一時ファイルを削除
                            os.remove(temp_file.name)

                            self.set_file_info(file=file, filename=uploadStatus.name, url=gcs_path, datatype=datatype,
                                               description=uploadStatus.description, size=new_gcs_blob.size)
                        except Exception as e:
                            logger.error(f"{e}: {traceback.format_exc()}")
                            self.set_file_upload_status_error_message(fileuploadstatus=uploadStatus, error_message="GCSへのアップロードに失敗しました。")
                            return Response({"message": "GCSへのアップロードに失敗しました。"},
                                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                        finally:
                            self.set_user_id(0)  # クリアしておく
                        contract.file.add(file)  # 契約書にファイルを紐付ける（save不要）
                    else:
                        self.set_file_upload_status_error_message(fileuploadstatus=uploadStatus, error_message=error_message)
                        return Response({"message": error_message}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    error_message = "ファイルがPDFではありません。"
                    self.set_file_upload_status_error_message(fileuploadstatus=uploadStatus, error_message=error_message)
                    return Response({"message": error_message}, status=status.HTTP_400_BAD_REQUEST)

            # QRコード付きPDFの場合は非同期処理は無いため、ここでアップロード完了となる
            self.set_file_upload_status_upload_status(fileuploadstatus=uploadStatus, upload_status=FileUploadStatus.UploadStatus.FINISHED.value)
            return Response(
                {"message": "契約書ID:" + str(qr_array["id"]) + " に紐付けされました。"},
                status=status.HTTP_200_OK
            )
        else:
            # ファイルアップロード
            try:
                logger.info(f"upload file size: {size}")
                if size >= int(settings.UPLOAD_PDF_FILE_SIZE_MAX):
                    max_size_mb = int(int(settings.UPLOAD_PDF_FILE_SIZE_MAX) / 1024 / 1024)
                    self.set_file_upload_status_error_message(
                        fileuploadstatus=uploadStatus,
                        error_message=f"{max_size_mb}MB以上のPDFファイルはメタ情報を抽出できないためアップロードできません。"
                    )
                    return Response(
                        {"message": "{max_size_mb}MB以上のPDFファイルはメタ情報を抽出できないためアップロードできません。"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                self.set_user_id(uploadStatus.user.id)
                client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
                file = self.prepare_file_record(0, uploadStatus.name, uploadStatus.type)
                # アップロード履歴とファイル情報を紐づける
                self.set_file_upload_status_file(fileuploadstatus=uploadStatus, file_id=file.id)
                _, gcs_path = self.get_gcs_fileinfo(file)
                new_gcs_blob = bucket.blob(gcs_path)  # GCS側

                # 一時ファイルを作成
                content = gcs_blob.download_as_string()
                with tempfile.NamedTemporaryFile(delete=True) as temp_file:
                    # 一時ファイルにデータを書き込み
                    temp_file.write(content)
                    # 一時ファイルをGCS Blobにアップロード
                    with open(temp_file.name, 'rb') as source_file:
                        new_gcs_blob.upload_from_file(source_file)  # local側

                self.set_file_info(file=file, filename=uploadStatus.name, url=gcs_path, datatype=uploadStatus.type,
                                   description=uploadStatus.description, size=new_gcs_blob.size)
            except Exception as e:
                logger.error(f"{e}: {traceback.format_exc()}")
                self.set_file_upload_status_error_message(fileuploadstatus=uploadStatus, error_message="GCSへのアップロードに失敗しました。")
                return Response({"message": "GCSへのアップロードに失敗しました。"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                self.set_user_id(0)  # クリアしておく

            # Contract を作る
            contract = self.create_contract(file, uploadStatus.user, uploadStatus)
            contract.file.add(file)  # Many to Many はIDが確定してから

            # Predict でメタ情報と本文を取得
            predict_file = PredictionRequestFile(
                id=uploadStatus.id,
                url=uploadStatus.file_path,
            )
            task_id: AsyncResult = prediction_on_upload_task.delay(
                predict_file_dict=predict_file.to_dict(),
                contract_id=contract.id,
                user_id=uploadStatus.user.id,
                datatype=uploadStatus.type,
                conpass_contract_type=uploadStatus.contract_type,
                is_meta_check=uploadStatus.is_meta_check == 1,
                renew_notify=uploadStatus.renew_notify,
                upload_id=uploadStatus.upload_id,
            )
            logger.info(f"Pushed contract prediction task: {task_id}")
            self.set_file_upload_status_task_id(fileuploadstatus=uploadStatus, task_id=task_id)

        return Response("登録が完了しました。", status=status.HTTP_200_OK)

    def create_contract(self, file, user, uploadStatus):
        now = make_aware(datetime.datetime.now())
        contract = Contract()
        contract.name = file.name
        status = Contract.Status.ENABLE.value
        type = file.type
        if type == ContractTypeable.ContractType.PAST.value:
            status = Contract.Status.SIGNED_BY_PAPER.value
            type = ContractTypeable.ContractType.CONTRACT.value
        elif type == ContractTypeable.ContractType.TEMPLATE.value:
            status = Contract.Status.UNUSED.value
        contract.type = type
        contract.account = user.account
        contract.directory_id = uploadStatus.directory_id
        contract.is_provider = True\
            if uploadStatus.is_provider and type == ContractTypeable.ContractType.TEMPLATE.value else False
        contract.is_open = True
        contract.status = status
        contract.created_at = now
        contract.created_by = user
        contract.updated_at = now
        contract.updated_by = user
        contract.save()
        if contract.type == ContractTypeable.ContractType.TEMPLATE.value:
            contract.template_id = contract.id  # 自分自身
        contract.origin_id = contract.id  # 自分自身
        contract.save()
        return contract
