import datetime
from django.db.models import Q, Prefetch
from django.db import transaction
from django.conf import settings
from django.utils.timezone import make_aware
from logging import getLogger

from conpass.models import Contract, File, FileUploadStatus, User
from conpass.models.constants.contractstatusable import ContractStatusable
from conpass.mailer.contract_upload_mailer import ContractUploadMailer
from conpass.services.gcp.cloud_storage import GoogleCloudStorage, GCSBucketName

logger = getLogger(__name__)


class CheckUploadResultService(GoogleCloudStorage):

    def check_upload_result(self, date: datetime.date):
        # 指定日にアップロードを失敗したユーザーの一覧を取得する
        logger.info(f"[{date}][start] check upload result")
        start_of_day = datetime.datetime(date.year, date.month, date.day, 0, 0, 0)
        end_of_day = datetime.datetime(date.year, date.month, date.day, 23, 59, 59)
        query = Q(
            upload_datetime__gte=start_of_day,
            upload_datetime__lt=end_of_day,
        )
        failed_user_list = FileUploadStatus.objects \
            .filter(query) \
            .exclude(upload_status=FileUploadStatus.UploadStatus.FINISHED.value) \
            .values('user') \
            .distinct()

        # 失敗したユーザーに対してメールを送信する
        user_ids = []
        for user in failed_user_list:
            # {'user': 4}
            user_ids.append(user['user'])
        send_user_list = User.objects.filter(id__in=user_ids).all()
        logger.info(f"send users: {user_ids}")
        for send_user in send_user_list:
            # メール送信
            ContractUploadMailer().send_upload_error_mail(user=send_user, date=date.strftime("%m月%d日"))
        logger.info(f"[{date}][end] check upload result, [send count] {send_user_list.count()}")

    def clean_failed_uploads(self, date: datetime.date):
        logger.info(f"[{date}][start] clean failed uploads")
        # アップロード履歴テーブルから以下の条件でレコードを抽出をする
        # ・created_atが対象期間内のレコード
        # ・created_atが現在時刻の1時間前より前を対象とする
        # ・ステータスが「アップロード中」または「失敗」のものを対象とする（UploadStatus.FINISHED 以外）
        # ※対象期間（現在時間より何秒前まで遡るか）は環境変数で指定する
        now = datetime.datetime.now()
        end_of_day = now - datetime.timedelta(hours=1)
        start_of_day = end_of_day - datetime.timedelta(seconds=int(settings.CLEANUP_PERIOD_FOR_FAILED_UPLOADS_SECONDS))
        logger.info(f"[start_of_day] {start_of_day} [end_of_day] {end_of_day}")
        query = Q(
            upload_datetime__gte=start_of_day,
            upload_datetime__lt=end_of_day,
        )
        failed_uploads = list(FileUploadStatus.objects
                              .filter(query)
                              .exclude(upload_status=FileUploadStatus.UploadStatus.FINISHED.value)
                              .all())
        logger.info(failed_uploads)

        for failed_upload in failed_uploads:
            # DBトランザクションをはる
            with transaction.atomic():
                # GCSにファイルが存在するかチェックして存在する場合は削除をする
                client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
                if failed_upload.file_path is not None and failed_upload.file_path != "" and failed_upload.file_id is not None:
                    # テンポラリファイルのファイルを削除
                    gcs_blob = bucket.blob(failed_upload.file_path)
                    if gcs_blob.exists():
                        gcs_blob.delete()

                    try:
                        file = File.objects \
                                   .exclude(status=Contract.Status.DISABLE.value) \
                                   .get(id=failed_upload.file_id)
                        # ファイルを削除
                        gcs_blob = bucket.blob(file.url)
                        if gcs_blob.exists():
                            gcs_blob.delete()

                        # Fileレコードを削除する
                        file.status = File.Status.DISABLE.value
                        file.updated_at = make_aware(datetime.datetime.now())
                        file.save()
                    except File.DoesNotExist:
                        logger.info(f"Fileレコードが見つかりません。 file_id={failed_upload.file_id}")

                    try:
                        contract = Contract.objects \
                                           .exclude(status=Contract.Status.DISABLE.value) \
                                           .filter(file__id=failed_upload.file_id) \
                                           .get()
                        # Contractレコードを削除する
                        contract.status = Contract.Status.DISABLE.value
                        contract.updated_at = make_aware(datetime.datetime.now())
                        contract.save()
                    except Contract.DoesNotExist:
                        logger.info(f"Contractレコードが見つかりません。 file_id={failed_upload.file_id}")
                    except Contract.MultipleObjectsReturned:
                        logger.info(f"Contractレコードが複数見つかりました。 file_id={failed_upload.file_id}")

                elif failed_upload.zip_path is not None and failed_upload.zip_path != "":
                    # zipファイルを削除
                    gcs_blob = bucket.blob(failed_upload.zip_path)
                    if gcs_blob.exists():
                        gcs_blob.delete()

                # アップロード履歴のステータスが「アップロード中」の場合は「失敗」に更新をする
                # error_messageカラムがNULLの場合、エラーを追加して「失敗」とする
                if failed_upload.error_message is None or failed_upload.error_message == "":
                    failed_upload.error_message = "アップロードに失敗しました。"
                    failed_upload.updated_at = make_aware(datetime.datetime.now())
                    failed_upload.save()

        logger.info(f"[{date}][end] clean failed uploads")
