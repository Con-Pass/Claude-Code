import datetime
import os
import urllib.parse
import traceback
import io
import zipfile
import json
import uuid
import threading
import tempfile
import pikepdf
from dateutil.relativedelta import relativedelta
from typing import Union
from logging import getLogger

from celery import shared_task
from celery.result import AsyncResult
from django.utils import html
from django.utils.timezone import make_aware
from django.db import DatabaseError
from django.conf import settings

from conpass.models import Contract, User, ContractBody, MetaData, MetaKey, File, FileUploadStatus
from conpass.models.constants import ContractTypeable
from conpass.services.contract.contract_service import ContractService, _tables_to_markdown
from conpass.services.gcp.cloud_storage import GoogleCloudStorage, GCSBucketName
from conpass.services.azure.azure_prediction import PredictionRequestFile, AzurePredict, PredictionResultFormat
from conpass.services.growth_verse.gv_prediction import GvPredictionRequestFile, GvPredict, GvPredictionResultFormat
from conpass.services.metadata.metadata_value_converter import MetadataValueConverter

from pdf2image import convert_from_path
from pdf2image.exceptions import PDFPageCountError
from pyzbar.pyzbar import decode, ZBarSymbol
from conpass.mailer.contract_upload_mailer import ContractUploadMailer

from common.utils.http_utils import execute_http_post
from conpass.services.contract.tasks import  notify_to_AI_agent
from conpass.services.contract.contract_enum import AIAgentNotifyEnum

META_RENEW_NOTIFY = 'conpass_contract_renew_notify'

logger = getLogger(__name__)


@shared_task
def prediction_on_upload_task(
    predict_file_dict: dict,
    contract_id: int,
    user_id: int,
    datatype,
    conpass_contract_type: str,
    is_meta_check: bool,
    renew_notify: int,
    upload_id: str,
):

    def execute(f_dict, cid, uid, d_type, c_type, is_meta, renew, upid):
        try:
            url = settings.PRIVATE_API_URL + '/private/task/execute/prediction-on-upload-task'
            data = {
                'predictFileId': f_dict['id'],
                'predictFileUrl': f_dict['url'],
                'contractId': cid,
                'userId': uid,
                'datatype': d_type,
                'conpassContractType': c_type,
                'isMetaCheck': is_meta,
                'renewNotify': renew,
                'uploadId': upid
            }
            execute_http_post(url, data)
        except Exception as e:
            logger.error(f"prediction_on_upload_task execute request error: {e}")
            file_upload_status = getFileUploadStatusByUploadId(upid)
            set_file_upload_status_error_message(file_upload_status, "ネットワークエラーが発生しました。")

    args = (predict_file_dict,
            contract_id,
            user_id,
            datatype,
            conpass_contract_type,
            is_meta_check,
            renew_notify,
            upload_id)
    thread = threading.Thread(target=execute, args=args)
    thread.start()
    return True


def prediction_on_upload_task_execute(
    predict_file_id: int,
    predict_file_url: str,
    contract_id: int,
    user_id: int,
    datatype,
    conpass_contract_type: str,
    is_meta_check: bool,
    renew_notify: int,
    upload_id: str,
):
    file_upload_status = getFileUploadStatusByUploadId(upload_id)
    set_file_upload_status_upload_status(file_upload_status, FileUploadStatus.UploadStatus.START_PREDICTION_ON_UPLOAD_TASK.value)
    try:
        if settings.GV_ENTITY_EXTRACTION_GPT_ENDPOINT:
            prediction = GvPredict()
            predict_file = GvPredictionRequestFile(predict_file_id, predict_file_url)
            prediction_result = prediction.get_predict(gcs_files=[predict_file], conpass_contract_type=conpass_contract_type,contract_id= contract_id)
        else:
            prediction = AzurePredict()
            predict_file = PredictionRequestFile(predict_file_id, predict_file_url)
            prediction_result = prediction.get_predict(gcs_files=[predict_file])
        contract = Contract.objects.get(id=contract_id)
        user = User.objects.get(id=user_id)

        service = ContractUploadPredictionService()
        # メタ情報に登録（必須）
        service.create_meta_data_type(contract, user, conpass_contract_type)
        # メタ情報に登録（メタ情報のチェック有の場合）
        # テンプレートの場合は、predictで抽出されたメタ情報は登録をしない
        if is_meta_check and datatype != ContractTypeable.ContractType.TEMPLATE.value:
            service.create_meta_data(prediction_result, contract, user)
        service.create_contract_body(prediction_result, contract, user)
        # メタ情報に登録（契約更新通知）
        if datatype == ContractTypeable.ContractType.PAST.value:
            service.create_meta_renew_notify(contract, user, renew_notify)

        set_file_upload_status_upload_status(file_upload_status, FileUploadStatus.UploadStatus.FINISHED.value)
        notify_to_AI_agent.delay([contract_id], AIAgentNotifyEnum.CREATED.value)
        return {
            'success': True,
        }
    except pikepdf._core.PdfError as e:
        logger.error(f"{e}: {traceback.format_exc()}")
        set_file_upload_status_error_message(file_upload_status, "アップロードしたファイルが破損しております。正常なファイルをご用意の上、再アップロードしてください。")
        raise
    except Exception as e:
        logger.error(f"{e}: {traceback.format_exc()}")
        set_file_upload_status_error_message(file_upload_status, "契約書本文の抽出またはメタ情報の抽出に失敗しました。")
        raise


@shared_task
def zip_upload_task(
    zip_file_path: str,
    bucket_type: str,
    user_id: int,
    conpass_contract_type: str,
    directory_id: int,
    is_provider: int,
    is_open: int,
    description: str,
    is_meta_check: bool,
    renew_notify: int,
    upload_id: str,
):

    def execute(zip_path, b_type, uid, c_type, did, is_prov,
                is_op, desc, is_meta, renew, upid):
        try:
            url = settings.PRIVATE_API_URL + '/private/task/execute/zip-upload-task'
            data = {
                'zipFilePath': zip_path,
                'bucketType': b_type,
                'userId': uid,
                'conpassContractType': c_type,
                'directoryId': did,
                'isProvider': is_prov,
                'isOpen': is_op,
                'description': desc,
                'isMetaCheck': is_meta,
                'renewNotify': renew,
                'uploadId': upid
            }
            execute_http_post(url, data)
        except Exception as e:
            logger.error(f"zip_upload_task execute request error: {e}")
            file_upload_status = getFileUploadStatusByUploadId(upid)
            set_file_upload_status_error_message(file_upload_status, "ネットワークエラーが発生しました。")

    args = (zip_file_path,
            bucket_type,
            user_id,
            conpass_contract_type,
            directory_id,
            is_provider,
            is_open,
            description,
            is_meta_check,
            renew_notify,
            upload_id)
    thread = threading.Thread(target=execute, args=args)
    thread.start()
    return True


def zip_upload_task_execute(
    zip_file_path: str,
    bucket_type: str,
    user_id: int,
    conpass_contract_type: str,
    directory_id: int,
    is_provider: int,
    is_open: int,
    description: str,
    is_meta_check: bool,
    renew_notify: int,
    upload_id: str,
):
    zip_upload_status = getFileUploadStatusByUploadId(upload_id)
    set_file_upload_status_upload_status(zip_upload_status, FileUploadStatus.UploadStatus.START_ZIP_UPLOAD_TASK.value)
    try:
        user = User.objects.get(id=user_id)
        cloudstorage_api = GoogleCloudStorage()
        bucket_name = GCSBucketName.FILE if bucket_type == 'file' else GCSBucketName.API
        client, bucket = cloudstorage_api.get_cloudstorage(bucket_name)
        blob = cloudstorage_api.get_blob(zip_file_path, bucket)
        fb = blob.download_as_bytes()

        with zipfile.ZipFile(io.BytesIO(fb)) as zf:
            cloudstorage_file = GoogleCloudStorage()
            for fileinfo in zf.infolist():

                # macの特殊ファイルディレクトリの場合はスキップ
                if fileinfo.filename.startswith('__MACOSX'):
                    continue

                _, ext = os.path.splitext(fileinfo.filename)
                if ext != ".pdf":
                    continue
                # windows で作成したzipファイルでPDFが日本語ファイル名だった場合の対策
                if not (fileinfo.flag_bits & 0x800):
                    try:
                        fileinfo.filename = fileinfo.orig_filename.encode('cp437').decode('cp932')
                    except UnicodeDecodeError:
                        fileinfo.filename = fileinfo.orig_filename.encode('cp437').decode('utf-8')

                fileinfo.filename = os.path.basename(fileinfo.filename)  # フォルダ名は含めない

                # 先にPDFファイルを保存する、Cloud Storageにファイルをアップロードする
                try:
                    pdf_upload_status = create_file_upload_status_record(
                        user_id,
                        fileinfo.filename,
                        description,
                        File.Type.PAST.value,  # この時点では仮置きとする
                        fileinfo.file_size,
                        directory_id,
                        conpass_contract_type,
                        renew_notify,
                        is_provider,
                        is_meta_check,
                        is_open,
                        upload_id
                    )
                    cloudstorage_file.set_user_id(user_id)
                    client, bucket = cloudstorage_file.get_cloudstorage(GCSBucketName.FILE)
                    file = cloudstorage_file.prepare_file_record(0, fileinfo.filename, File.Type.PAST.value)
                    _, gcs_path = cloudstorage_file.get_gcs_fileinfo(file)
                    gcs_blob = bucket.blob(gcs_path)
                    with zf.open(fileinfo, "r") as f:
                        gcs_blob.upload_from_file(file_obj=f)
                        cloudstorage_file.set_file_info(
                            file=file,
                            filename=fileinfo.filename,
                            url=gcs_path,
                            datatype=File.Type.PAST.value,  # この時点では仮置きとする,
                            description=description,
                            size=fileinfo.file_size
                        )
                    set_file_upload_status_file(pdf_upload_status, file.id)
                    set_file_upload_status_file_path(pdf_upload_status, gcs_path)
                except Exception as e:
                    logger.error(f"{e}: {traceback.format_exc()}")
                    set_file_upload_status_error_message(pdf_upload_status, f"ファイル保存エラー: {fileinfo.filename}")
                    return {
                        'success': False
                    }
                finally:
                    cloudstorage_file.set_user_id(0)  # クリアしておく

                # 別タスクでPDFファイルにQRコードが含まれているか解析する
                task_id: AsyncResult = classify_by_qr_code_presence_task.delay(
                    zip_upload_id=upload_id,
                    pdf_upload_id=pdf_upload_status.upload_id,
                    user_id=user.id,
                    conpass_contract_type=conpass_contract_type,
                    directory_id=directory_id
                )
                logger.info(f"Pushed contract prediction task: {task_id}")

        set_file_upload_status_upload_status(zip_upload_status, FileUploadStatus.UploadStatus.FINISHED.value)
        return {'success': True}
    except Exception as e:
        logger.error(f"{e}: {traceback.format_exc()}")
        set_file_upload_status_error_message(zip_upload_status, "zipファイルの展開に失敗しました。")
        raise


@shared_task
def classify_by_qr_code_presence_task(
    zip_upload_id: str,
    pdf_upload_id: str,
    user_id: int,
    conpass_contract_type: str,
    directory_id: int
):
    def execute(zupid, pupid, uid, c_type, did):
        try:
            url = settings.PRIVATE_API_URL + '/private/task/execute/classify-by-qr-code-presence-task'
            data = {
                'zipUploadId': zupid,
                'pdfUploadId': pupid,
                'userId': uid,
                'conpassContractType': c_type,
                'directoryId': did
            }
            execute_http_post(url, data)
        except Exception as e:
            logger.error(f"zip_upload_task classify_by_qr_code_presence_task request error: {e}")
            pdf_upload_status = getFileUploadStatusByUploadId(pupid)
            set_file_upload_status_error_message(pdf_upload_status, "ネットワークエラーが発生しました。")
            zip_upload_status = getFileUploadStatusByUploadId(zupid)
            set_file_upload_status_error_message(zip_upload_status, "ネットワークエラーが発生しました。")

    args = (zip_upload_id,
            pdf_upload_id,
            user_id,
            conpass_contract_type,
            directory_id)
    thread = threading.Thread(target=execute, args=args)
    thread.start()
    return True


def classify_by_qr_code_presence_task_execute(
    zip_upload_id: str,
    pdf_upload_id: str,
    user_id: int,
    conpass_contract_type: str,
    directory_id: int
):
    pdf_upload_status = getFileUploadStatusByUploadId(pdf_upload_id)
    set_file_upload_status_upload_status(pdf_upload_status, FileUploadStatus.UploadStatus.START_CLASSIFY_BY_QR_CODE_PRESENCE.value)
    user = User.objects.get(id=user_id)
    cloudstorage_api = GoogleCloudStorage()
    client, bucket = cloudstorage_api.get_cloudstorage(GCSBucketName.FILE)
    gcs_blob = bucket.blob(pdf_upload_status.file_path)  # GCSにアップロードされたファイル

    datatype = File.Type.PAST.value  # datatype の初期値は PAST
    is_qr_code = False  # QRコードを含むファイルかどうかのフラグ
    is_not_permission = False  # 権限がないファイルかどうかのフラグ
    is_upload = True  # ファイルをアップロードするかどうかのフラグ

    # QRコードを含むファイルかチェック
    # 一時ファイルを作成
    content = gcs_blob.download_as_string()
    with tempfile.NamedTemporaryFile(delete=True) as temp_file:
        # 一時ファイルにデータを書き込み
        temp_file.write(content)

        try:
            pages = convert_from_path(temp_file.name)
        except PDFPageCountError:
            # ページ数が0の場合はエラーとする
            set_file_upload_status_error_message(fileuploadstatus=pdf_upload_status, error_message="0ページのPDFファイルです。")
            return {'success': False}

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
                    is_upload = False  # ディレクトリのパーミッションがない、サービス外のQRコードの場合はアップロードしない
                    is_not_permission = True  # 権限がないファイルの場合は True
                    continue  # QRコードのデータがJSON形式ではない場合はスキップ
                if not isinstance(qr_array, dict):
                    is_upload = False  # ディレクトリのパーミッションがない、サービス外のQRコードの場合はアップロードしない
                    is_not_permission = True  # 権限がないファイルの場合は True
                    continue  # QRコードのデータが辞書型ではない場合はスキップ
                if "id" in qr_array:
                    # QRコードを読み取り取得したデータから紐付ける Contract を抽出する
                    wheres = {
                        'id': qr_array["id"],
                        'account': user.account
                    }
                    contract = is_contract_exist(wheres=wheres)
                    if contract:
                        datatype = File.Type.CONTRACT_QR.value  # datatype を ETC に変更
                        is_qr_code = True  # QRコードを含むファイルの場合は True
                        is_upload = True  # QRコードを含むファイルの場合は True
                        break
                is_upload = False  # ディレクトリのパーミッションがない、サービス外のQRコードの場合はアップロードしない
                is_not_permission = True  # 権限がないファイルの場合は True

    set_file_upload_status_upload_status(pdf_upload_status, FileUploadStatus.UploadStatus.COMPLETE_CLASSIFY_BY_QR_CODE_PRESENCE.value)
    if is_upload:
        # ファイルをアップロードは、zipの解凍時に行われているため、
        # ここでは仮置きされているFileUploadStatusとFileのdatatypeの更新を行う
        set_file_upload_status_datatype(pdf_upload_status, datatype)
        file = pdf_upload_status.file
        file.type = datatype
        file.save()

        if is_qr_code:
            # QRコードを含むファイルの場合は契約書にファイルを紐付ける
            contract.file.add(file)  # 契約書にファイルを紐付ける（save不要）
            success_qr_file_list_str = f'契約書ID: {qr_array["id"]} {file.name}'
            logger.info(f"Success: link QR file and contract. {success_qr_file_list_str}")

            # QRコードの場合は解析が無いため、ここでPDFファイルアップロード完了とする
            set_file_upload_status_upload_status(pdf_upload_status, FileUploadStatus.UploadStatus.FINISHED.value)
        else:
            if pdf_upload_status.size > int(settings.UPLOAD_PDF_FILE_SIZE_MAX):
                max_size_mb = int(int(settings.UPLOAD_PDF_FILE_SIZE_MAX) / 1024 / 1024)
                logger.warn(f"ファイルサイズが{max_size_mb}MBを超えています。")
                set_file_upload_status_error_message(pdf_upload_status, f"ファイルサイズが{max_size_mb}MBを超えています。")
                return {'success': False}

            set_file_upload_status_upload_status(pdf_upload_status, FileUploadStatus.UploadStatus.COMPLETE_SAVE_PDF_FROM_ZIP.value)

            # QRコードを含まないファイルの場合は新規に契約書を作成する
            # Contract を作る
            service = ContractUploadPredictionService()
            contract = service.create_contract(
                file,
                user,
                directory_id,
                pdf_upload_status.is_provider,
                pdf_upload_status.is_open,
                pdf_upload_status.zip_path)
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
                is_meta_check=pdf_upload_status.is_meta_check,
                renew_notify=pdf_upload_status.renew_notify,
                upload_id=pdf_upload_status.upload_id
            )
            logger.info(f"Pushed contract prediction task: {task_id}")
            set_file_upload_status_task_id(fileuploadstatus=pdf_upload_status, task_id=task_id)
    else:
        if is_not_permission:
            set_file_upload_status_error_message(pdf_upload_status, "PDF内にあるQRコードがConPass用のQRコード形式と異なるためアップロードできません。")
        else:
            set_file_upload_status_error_message(pdf_upload_status, "ファイルの解析に失敗しました。")
        return {'success': False}
    return {'success': True}


def is_contract_exist(wheres):
    """
    Contract が存在するか確認する
    """
    try:
        contract = Contract.objects.exclude(status=Contract.Status.DISABLE.value).filter(**wheres).get()
        return contract
    except Contract.DoesNotExist as e:
        logger.info(e)
        return None


def send_mail_for_bulk_upload(
    user: User,
    success_qr_file_list=None,
    success_file_number=0,
    error_permission_list=None,
    error_file_list=None
):
    """
    一括アップロードの結果をメール送信
    """
    # データの整形
    body = "締結済の契約書ファイル\n・" + str(success_file_number) + "件\n\n"
    if success_qr_file_list:
        list = "\n".join(f"・{item}" for item in success_qr_file_list)
        body += "QRコード付き契約書ファイル\n" + list + "\n\n"
    else:
        body += "QRコード付き契約書ファイル\nなし\n\n"
    if error_file_list:
        list = "\n".join(f"・{item}" for item in error_file_list)
        body += "取り込みエラー（ファイル容量20MB以上）\n" + list
    else:
        body += "取り込みエラー（ファイル容量20MB以上）\nなし"
    if error_permission_list:
        list = "\n".join(f"・{item}" for item in error_permission_list)
        body += "\n\n紐付けエラー（QRコード読取不可・対象レコード不明）\n" + list
    else:
        body += "\n\n紐付けエラー（QRコード読取不可・対象レコード不明）\nなし"

    # メール送信
    ContractUploadMailer().send_bulk_upload_result_mail(user=user, body=body)


def create_file_upload_status_record(
    user_id: int,
    filename: str,
    description: str,
    filetype: int,
    size: int,
    directory_id: int,
    contract_type: str,
    renew_notify: int,
    is_provider: int,
    is_meta_check: int,
    is_open: int,
    zip_upload_id: str
):
    user = User.objects.select_related('account').filter(id=user_id).get()
    account_id = user.account_id
    now = make_aware(datetime.datetime.now())
    fileuploadstatus = FileUploadStatus(
        upload_id=str(uuid.uuid4()),
        task_id="",
        name=filename,
        description=description,
        type=filetype,
        size=size,
        upload_datetime=now,
        upload_status=FileUploadStatus.UploadStatus.START_SAVE_PDF_FROM_ZIP.value,
        file_path="",
        zip_path="",
        directory_id=directory_id,
        contract_type=contract_type,
        renew_notify=renew_notify,
        is_provider=is_provider,
        is_meta_check=is_meta_check,
        is_open=is_open,
        zip_id=zip_upload_id,
        status=FileUploadStatus.Status.ENABLE.value,
        account_id=account_id,
        user_id=user_id,
        created_at=now,
        created_by_id=user_id,
        updated_at=now,
        updated_by_id=user_id)
    fileuploadstatus.save()
    return fileuploadstatus


def getFileUploadStatusByUploadId(upload_id):
    if upload_id is None:
        return None
    try:
        wheres = {'upload_id': upload_id}
        uploadStatus = FileUploadStatus.objects.filter(**wheres).get()
    except FileUploadStatus.DoesNotExist as e:
        logger.error(f"{e}: {traceback.format_exc()}")
        uploadStatus = None
    return uploadStatus


def set_file_upload_status_file_path(fileuploadstatus: FileUploadStatus, file_path: int):
    if fileuploadstatus is None:
        return
    now = make_aware(datetime.datetime.now())
    fileuploadstatus.file_path = file_path
    fileuploadstatus.updated_at = now
    fileuploadstatus.updated_by_id = fileuploadstatus.user.id
    fileuploadstatus.save()


def set_file_upload_status_upload_status(fileuploadstatus: FileUploadStatus, upload_status: int):
    if fileuploadstatus is None:
        return
    now = make_aware(datetime.datetime.now())
    fileuploadstatus.upload_status = upload_status
    fileuploadstatus.updated_at = now
    fileuploadstatus.updated_by_id = fileuploadstatus.user.id
    fileuploadstatus.save()


def set_file_upload_status_error_message(fileuploadstatus: FileUploadStatus, error_message: str):
    # エラーが設定されている場合は上書きは行わないようにする
    if fileuploadstatus is None or fileuploadstatus.error_message != "":
        return
    now = make_aware(datetime.datetime.now())
    fileuploadstatus.error_message = error_message
    fileuploadstatus.updated_at = now
    fileuploadstatus.updated_by_id = fileuploadstatus.user.id
    fileuploadstatus.save()


def set_file_upload_status_task_id(fileuploadstatus: FileUploadStatus, task_id: str):
    if fileuploadstatus is None:
        return
    now = make_aware(datetime.datetime.now())
    fileuploadstatus.task_id = task_id
    fileuploadstatus.updated_at = now
    fileuploadstatus.updated_by_id = fileuploadstatus.user.id
    fileuploadstatus.save()


def set_file_upload_status_file(fileuploadstatus: FileUploadStatus, file_id: int):
    if fileuploadstatus is None:
        return
    now = make_aware(datetime.datetime.now())
    fileuploadstatus.file_id = file_id
    fileuploadstatus.updated_at = now
    fileuploadstatus.updated_by_id = fileuploadstatus.user.id
    fileuploadstatus.save()


def set_file_upload_status_datatype(fileuploadstatus: FileUploadStatus, datatype: int):
    if fileuploadstatus is None:
        return
    now = make_aware(datetime.datetime.now())
    fileuploadstatus.type = datatype
    fileuploadstatus.updated_at = now
    fileuploadstatus.updated_by_id = fileuploadstatus.user.id
    fileuploadstatus.save()


class ContractUploadPredictionService:
    def create_contract(self, file, user, directory_id, is_provider, is_open, zip_path):
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
        contract.directory_id = directory_id
        contract.is_provider = True \
            if is_provider and type == ContractTypeable.ContractType.TEMPLATE.value else False
        contract.is_open = is_open
        contract.bulk_zip_path = zip_path
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

    def create_contract_body(self, predictions_per_files: Union[PredictionResultFormat, GvPredictionResultFormat], contract, user):
        file = predictions_per_files.get("files")[0]  # ファイル単位なので１ファイル目をつかう
        body = file.get("body")

        now = make_aware(datetime.datetime.now())
        contract_body = ContractBody()
        contract_body.contract = contract
        # <table> を Markdown に変換（GV_OCR / 非GV_OCR 両パスで適用）
        body = _tables_to_markdown(body)
        # GrowthVerse APIで全文抽出をしている場合は、HTML形式で全文抽出をしているためタグの削除およびpタグの追加は行わない
        if not (settings.GV_OCR_GEMINI_ENDPOINT and file.get("pdf_page_size") <= 100):
            body = html.strip_tags(body)
            body = "<p>" + "</p><p>".join(body.splitlines()) + "</p>"
        contract_body.body = urllib.parse.quote(body)
        contract_body.status = ContractBody.Status.ENABLE.value
        contract_body.created_at = now
        contract_body.created_by = user
        contract_body.updated_at = now
        contract_body.updated_by = user
        contract_body.version = "1.0"
        contract_body.is_adopted = contract.type == ContractTypeable.ContractType.TEMPLATE.value
        contract_body.save()

        # 全検索用モデルとMeilisearchに保存
        try:
            contract_service = ContractService()
            contract_service.save_contract_body_search_task(contract_body, now)
        except Exception as e:
            logger.error(f"contract_body_search error:{e}")

    def create_meta_data_type(self, contract, user, conpass_contract_type):
        now = make_aware(datetime.datetime.now())
        # 契約種別
        metadata = MetaData()
        metadata.contract = contract
        try:
            metakey = MetaKey.objects.get(label='conpass_contract_type', type=MetaKey.Type.DEFAULT.value,
                                          status=MetaKey.Status.ENABLE.value)
        except MetaKey.DoesNotExist as e:
            logger.info(e)
        else:
            metadata.key = metakey
            metadata.value = conpass_contract_type
            metadata.status = MetaData.Status.ENABLE.value
            metadata.created_at = now
            metadata.created_by = user
            metadata.updated_at = now
            metadata.updated_by = user
            metadata.save()

        # 担当者名
        metadata = MetaData()
        metadata.contract = contract
        try:
            metakey = MetaKey.objects.get(label='conpass_person', type=MetaKey.Type.DEFAULT.value,
                                          status=MetaKey.Status.ENABLE.value)
        except MetaKey.DoesNotExist as e:
            logger.info(e)
        else:
            metadata.key = metakey
            metadata.value = ''  # アップロード時は空欄（担当者未割り当て）で登録
            metadata.status = MetaData.Status.ENABLE.value
            metadata.created_at = now
            metadata.created_by = user
            metadata.updated_at = now
            metadata.updated_by = user
            metadata.save()

        return

    def create_meta_data(self, predictions_per_files: Union[PredictionResultFormat, GvPredictionResultFormat], contract, user):
        now = make_aware(datetime.datetime.now())
        file = predictions_per_files.get("files")[0]  # ファイル単位なので１ファイル目をつかう
        predictions = file.get("predictions")
        reckoning_dates = []  # 起算日候補を格納するリスト
        cd_reckoning_dates = []  # contractdateを格納するリスト
        csd_reckoning_dates = []  # contractstartdateを格納するリスト
        ceds = []  # contractenddateを格納するリスト
        ced_date_values = []  # contractenddateのdate_valueを格納するリスト
        contract_period = []  # contractenddateを算出するための期間リスト
        cn = MetaData()  # cancelnoticeを格納する変数
        notice_period = []  # cancelnoticeを算出するための期間リスト
        is_aud = 0  # autoupdateが登録されたか判別する変数
        temp = []  # 重複登録のチェック用
        cancel_notice_date=''
        for predict in predictions:
            metadata = MetaData()
            metadata.contract = contract
            if predict.get("entity")=='cancelnotice_date':
                cancel_notice_date = predict.get("content")
                logger.info(f"found cancel_notice_date:{cancel_notice_date}")
            try:
                metakey = MetaKey.objects.get(label=predict.get("entity"), type=MetaKey.Type.DEFAULT.value,
                                              status=MetaKey.Status.ENABLE.value)
            except MetaKey.DoesNotExist as e:
                logger.info(e)
                continue
            metadata.key = metakey
            metadata.value = predict.get("content")
            metadata.score = predict.get("score")
            metadata.start_offset = predict.get("start")
            metadata.end_offset = predict.get("end")
            metadata.status = MetaData.Status.ENABLE.value
            metadata.created_at = now
            metadata.created_by = user
            metadata.updated_at = now
            metadata.updated_by = user
            # メタ情報が契約書名の場合、contract.nameも更新する
            if metadata.key.label == 'title':
                self._update_contract_name(user, metadata, contract, now)
            metadata_value_converter = MetadataValueConverter()
            converted_metadata = metadata_value_converter.convert(metadata)

            # key.labelとvalueを連結して同じデータを登録済みの場合は登録をスキップする
            new_key_val = '-'.join([converted_metadata.key.label, converted_metadata.value])
            if new_key_val in temp:
                continue
            temp.append(new_key_val)

            # メタ情報が契約日の場合、リストに格納する
            if metadata.key.label == 'contractdate':
                if converted_metadata.date_value is not None:
                    cd_reckoning_dates.append(converted_metadata.date_value)
            # メタ情報が契約開始日の場合、リストに格納する
            if metadata.key.label == 'contractstartdate':
                if converted_metadata.date_value is not None:
                    csd_reckoning_dates.append(converted_metadata.date_value)
            # メタ情報が契約終了日もしくは解約ノーティスの場合、データを変数へ格納し後ほど処理をする
            if metadata.key.label == 'contractenddate':
                ceds.append(converted_metadata)
            elif metadata.key.label == 'cancelnotice':
                cn = converted_metadata
            else:
                converted_metadata.save()
                # メタ情報が自動更新の場合は判別変数を1にする
                if metadata.key.label == 'autoupdate':
                    is_aud = 1

        # 契約終了日を処理する
        for ced in ceds:
            # 契約終了日を日付として抽出できていない場合は文章から日付に変換を行う
            if ced.date_value is None and len(ced.value) > 0:
                metadata_value_converter = MetadataValueConverter()
                if metadata_value_converter.check_pattern(ced.value,
                                                          r'(締結日|締結の日|締結後|本日|発行日|西暦)') == '1':
                    # 契約日が取得できているか判断する
                    if cd_reckoning_dates:
                        reckoning_dates = sorted(cd_reckoning_dates)  # 昇順で起算日リストをソートする
                elif metadata_value_converter.check_pattern(ced.value, r'(開始|開始する)日') == '1':
                    # 契約開始日が取得できているか判断する
                    if csd_reckoning_dates:
                        reckoning_dates = sorted(csd_reckoning_dates)  # 昇順で起算日リストをソートする
                if reckoning_dates:
                    # 契約終了日の文字列の中に期間が含まれているか判断する
                    if metadata_value_converter.check_pattern(ced.value, r'([0-9]+)(カ年|ヵ年|か年|ヶ年|ケ年|年|カ月|ヵ月|か月|ヶ月|ケ月|月|日)') == '1':
                        contract_period = metadata_value_converter.regexp_period(ced.value)
                        if contract_period and contract_period[0] > 0:
                            if contract_period[1] == 'year':
                                # 年数を加算して1日減算する
                                ced.date_value = reckoning_dates[0] + relativedelta(
                                    years=contract_period[0]) + relativedelta(days=-1)
                            elif contract_period[1] == 'month':
                                # 月数を加算して1日減算する
                                ced.date_value = reckoning_dates[0] + relativedelta(
                                    months=contract_period[0]) + relativedelta(days=-1)
                            elif contract_period[1] == 'day':
                                ced.date_value = reckoning_dates[0] + relativedelta(days=contract_period[0])

            # 契約終了日の日付が抽出できた場合は、後続の解約ノーティス変換処理で利用するためにデータを保持する
            if ced.date_value is not None:
                ced_date_values.append(ced.date_value)

            # contractenddateを保存する
            ced.save()

        # cancelnoticeを処理する
        # 取得したすべてのcontractenddateの日付データが同一か判断
        if ced_date_values and ced_date_values.count(ced_date_values[0]) == len(
                ced_date_values) and cn.value is not None:
            metadata_value_converter = MetadataValueConverter()
            if cancel_notice_date:
                cnd=metadata_value_converter.regexp_ymd_hs(text=cancel_notice_date)
                if isinstance(cnd, datetime.datetime):
                    cn.date_value= cnd
            if not cn.date_value:
                try:
                    if metadata_value_converter.check_pattern(cn.value, r'([0-9]+)(カ年|ヵ年|か年|ヶ年|ケ年|年|カ月|ヵ月|か月|ヶ月|ケ月|月)') == '1':
                        if metadata_value_converter.check_pattern(cn.value, r'(迄|まで|前|まえ|以上)') == '1':
                            notice_period = metadata_value_converter.regexp_period(cn.value)
                            if notice_period and notice_period[0] > 0:
                                if notice_period[1] == 'year':
                                    # 年数を減算する
                                    cn.date_value = ced_date_values[0] + relativedelta(years=-notice_period[0])
                                elif notice_period[1] == 'month':
                                    # 月数を減算する
                                    cn.date_value = ced_date_values[0] + relativedelta(months=-notice_period[0])
                except Exception as e:
                    logger.info("Could not extract cancel notice date: {}".format(e))

        # cancelnoticeを保存する
        cn.save()

        # autoupdateを処理する
        # autoupdateの情報がない場合はautoupdateを初期値'0'で保存
        if is_aud == 0:
            metadata_aud = MetaData()
            metadata_aud.contract = contract
            try:
                metakey_aud = MetaKey.objects.get(label='autoupdate', type=MetaKey.Type.DEFAULT.value,
                                                  status=MetaKey.Status.ENABLE.value)
            except MetaKey.DoesNotExist as e:
                logger.info(e)
            else:
                metadata_aud.key = metakey_aud
                metadata_aud.value = '0'  # 初期値'0'をセット
                metadata_aud.status = MetaData.Status.ENABLE.value
                metadata_aud.created_at = now
                metadata_aud.created_by = user
                metadata_aud.updated_at = now
                metadata_aud.updated_by = user
                metadata_aud.save()

        return

    def _update_contract_name(self, user, metadata, contract, now):
        try:
            contract.name = metadata.value
            contract.updated_at = now
            contract.updated_by = user
        except Contract.DoesNotExist as e:
            logger.info(e)

    def create_meta_renew_notify(self, contract, user, renew_notify):
        now = make_aware(datetime.datetime.now())
        try:
            metakey = MetaKey.objects.get(label=META_RENEW_NOTIFY, type=MetaKey.Type.DEFAULT.value,
                                          status=MetaKey.Status.ENABLE.value)
        except MetaKey.DoesNotExist as e:
            logger.info(e)
            return

        metadata = MetaData()
        metadata.contract = contract
        metadata.key = metakey
        metadata.value = '1' if renew_notify else '0'
        metadata.created_at = now
        metadata.created_by = user
        metadata.updated_at = now
        metadata.updated_by = user
        metadata.save()

        return
