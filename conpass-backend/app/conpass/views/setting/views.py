import traceback
import csv
import datetime
import time

from django.forms.models import model_to_dict
from django.http import HttpResponse
from logging import getLogger

from rest_framework import status, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from conpass.models import MetaKey, MetaData, Directory, MetaKeyDirectory, Contract
from django.db.models import Prefetch, Q, F, Value
from django.db.models.functions import Coalesce
from collections import OrderedDict

from django.utils.timezone import make_aware
from django.utils import timezone
from django.utils.dateparse import parse_date

from django.db import connection, transaction

from conpass.services.metadata.metadata_csv_service import MetadataCsvService
from conpass.views.setting.serializer.setting_meta_download_serializer import SettingMetaDownloadRequestSerializer, SettingContractMetaDownloadRequestSerializer
from conpass.views.setting.serializer.setting_serializer import SettingRequestBodySerializer, \
    SettingResponseSerializer, SettingResponseBodySerializer, SettingRequestCSVBodySerializer
from conpass.views.setting.serializer.setting_directory_serializer import SettingDirectoryResponseBodySerializer
from conpass.views.setting.serializer.setting_directory_meta_serializer import \
    SettingDirectoryMetaResponseBodySerializer, SettingDirectoryMetaRequestBodySerializer
from django.db.utils import DatabaseError
from conpass.models.constants import ContractTypeable, Statusable
from conpass.models.constants.contractstatusable import ContractStatusable
from conpass.models.company_meta_key import CompanyMetaKey

logger = getLogger(__name__)

# 日付の値も登録が必要なmetakey.idのリスト
METAKEY_IDS_OF_DATE = [6, 7, 8, 10, 13]


class SettingMetaView(APIView):
    """
    全体共通のメタ情報取得
    """

    def get(self, request):
        account=request.user.account
        meta_keys=[]
        company_meta_keys={
            cmk.meta_key_id: cmk
                for cmk in CompanyMetaKey.objects.filter(account=account)
        }
        default_meta_keys=list(MetaKey.objects.filter(status=MetaKey.Status.ENABLE.value, type= MetaKey.Type.DEFAULT.value).values())
        for default_meta_key in default_meta_keys:
            cmk= company_meta_keys.get(default_meta_key['id'])
            if cmk:
                default_meta_key['is_visible'] = cmk.is_visible
                default_meta_key['accountId'] = cmk.account_id

            else:
                default_meta_key['accountId'] = None

            meta_keys.append(default_meta_key)

        default_meta_keys = list(MetaKey.objects.filter(status=MetaKey.Status.ENABLE.value, type=MetaKey.Type.FREE.value, account=account).values())
        meta_keys.extend(default_meta_keys)


        res_serializer = SettingResponseBodySerializer(meta_keys)
        return Response(data=res_serializer.data)


class SettingMetaUpdateView(APIView):
    """
    全体共通のメタ情報更新
    """

    def post(self, request):
        req_serializer = SettingRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = self.request.user
        account= user.account
        setting_meta = req_serializer.data.get('settingMeta')
        free_key_count=0
        for data in setting_meta:
            if data.get('type') == MetaKey.Type.FREE.value:
                if data.get('status') == Statusable.Status.ENABLE.value:
                    free_key_count+=1

        if free_key_count > 10:
            return Response({"msg": ["自由項目は10個まで登録可能です"]}, status.HTTP_400_BAD_REQUEST)

        for data in setting_meta:
            if data.get('type') == MetaKey.Type.DEFAULT.value:
                obj, created=CompanyMetaKey.objects.update_or_create(
                    account=account, meta_key_id= data.get('id'),
                    defaults={'is_visible': data.get('is_visible'),
                              'status': CompanyMetaKey.Status.ENABLE.value,
                              'updated_at':  make_aware(datetime.datetime.now()),
                              'updated_by': user,
                              }
                )
                if created:
                    obj.created_by = user
                    obj.created_at= make_aware(datetime.datetime.now())
                    obj.save()

            if data.get('type') == MetaKey.Type.FREE.value:
                if data.get('id')==0:
                    MetaKey.objects.create(
                        account=account,
                        name= data.get('name'),
                        type= data.get('type'),
                        is_visible=data.get('is_visible'),
                        status=data.get('status'),
                        updated_at=make_aware(datetime.datetime.now()),
                        updated_by=user,
                        created_at= make_aware(datetime.datetime.now()),
                        created_by=user
                    )
                else:
                    updatable_meta_key=MetaKey.objects.filter(id=data.get('id'), account=account).first()
                    if updatable_meta_key:
                        updatable_meta_key.name = data.get('name')
                        updatable_meta_key.is_visible = data.get('is_visible')
                        updatable_meta_key.updated_at= make_aware(datetime.datetime.now())
                        updatable_meta_key.updated_by = user
                        updatable_meta_key.status = data.get('status')
                        updatable_meta_key.save()


        return Response({"msg": ["設定を更新しました"]}, status.HTTP_200_OK)




class SettingMetaCSVUpdateView(APIView):
    """
    CSV一括更新
    """

    def post(self, request):
        req_serializer = SettingRequestCSVBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        error_list = []
        try:
            csv_setting_meta = req_serializer.data.get('csvSettingMeta')
            for index, csv_meta in enumerate(csv_setting_meta):
                csv_meta['lineNum'] = index + 2
                try:
                    if csv_meta.get('metadataId'):
                        self._update_meta_data(csv_meta)
                    else:
                        self._create_meta_data(csv_meta)
                except self.CsvRowItemError as e:
                    error_list.append(e.csv_meta)
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.info("取り込み失敗一覧", extra={"error_list": error_list})
        return Response({"msg": ["設定を更新しました"], "error_list": error_list}, status.HTTP_200_OK)

    def _update_meta_data(self, csv_meta: dict):
        try:
            meta_data = MetaData.objects.select_related('key').get(
                pk=csv_meta.get('metadataId'),
                contract__account_id=self.request.user.account_id,
                status=MetaData.Status.ENABLE.value,
            )
        except MetaData.DoesNotExist:
            csv_meta["reason"] = "存在しないメタデータIDです"
            raise self.CsvRowItemError(csv_meta)
        if meta_data.lock:
            csv_meta["reason"] = "ロックされています"
            raise self.CsvRowItemError(csv_meta)
        meta_data.value = csv_meta.get('value')
        if csv_meta["metakeyId"] in METAKEY_IDS_OF_DATE and csv_meta["dateValue"]:
            try:
                meta_data.date_value = datetime.datetime.strptime(csv_meta["dateValue"], '%Y-%m-%d')
            except ValueError:
                csv_meta["reason"] = "日付のフォーマットはYYYY-MM-DDです"
                raise self.CsvRowItemError(csv_meta)
        meta_data.updated_by_id = self.request.user.id
        meta_data.updated_at = make_aware(datetime.datetime.now())
        meta_data.save()

    def _create_meta_data(self, csv_meta: dict):
        try:
            contract = Contract.objects.exclude(
                status=Contract.Status.DISABLE.value,
            ).get(
                id=csv_meta.get('contractId'),
                account_id=self.request.user.account_id,
            )
            meta_key = MetaKey.objects.get(
                id=csv_meta.get('metakeyId'),
                account_id=self.request.user.account_id,
                status=MetaKey.Status.ENABLE.value,
            )
            date_value = None
            if csv_meta["metakeyId"] in METAKEY_IDS_OF_DATE and csv_meta["dateValue"]:
                date_value = datetime.datetime.strptime(csv_meta["dateValue"], '%Y-%m-%d')
            new_metadata = MetaData(
                contract=contract,
                key=meta_key,
                status=MetaData.Status.ENABLE.value,
                value=csv_meta.get('value'),
                date_value=date_value,
                created_by=self.request.user,
                updated_by=self.request.user,
            )
        except Contract.DoesNotExist:
            csv_meta["reason"] = "存在しない契約IDです"
            raise self.CsvRowItemError(csv_meta)
        except MetaKey.DoesNotExist:
            csv_meta["reason"] = "存在しないメタキーIDです"
            raise self.CsvRowItemError(csv_meta)
        except ValueError:
            csv_meta["reason"] = "日付のフォーマットはYYYY-MM-DDです"
            raise self.CsvRowItemError(csv_meta)
        new_metadata.save()

    class CsvRowItemError(Exception):
        def __init__(self, csv_meta: dict):
            self.csv_meta = csv_meta


class SettingMetaCSVDownloadView(APIView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.metadata_service = MetadataCsvService()

    def get(self, request):
        """
        自由項目ダウンロード処理
        """
        try:
            req_serializer = SettingMetaDownloadRequestSerializer(data=request.query_params)
            if not req_serializer.is_valid():
                return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            meta_key_ids = list(map(int, req_serializer.data.get('metaKeyIds').split(',')))
            generator = self.metadata_service.get_metadata_csv_generator(
                account=self.request.user.account,
                meta_key_ids=meta_key_ids,
            )

            logger.info("メタ情報のCSV化")
            logger.info(f"アカウントID:{self.request.user.account.id}")
            logger.info(f"metakey:{meta_key_ids}")

            t_delta = datetime.timedelta(hours=9)
            jst = datetime.timezone(t_delta, 'JST')
            now = datetime.datetime.now(jst)
            file_name = 'conpass_metadata_{file_date}'.format(file_date=now.strftime('%Y%m%d%H%M%S'))
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="{file_name}.csv"'.format(file_name=file_name)
            writer = csv.writer(response, quotechar='"')

            # CSVの内容を編集し、行数をカウント
            writer.writerow(['契約書ID（変更不可）', 'メタキーID（変更不可）', 'メタデータID（変更不可）', '項目名（変更不可）', '値', '値（日付）'])
            count = 0  # 行数カウント用
            for data in generator:
                writer.writerow([
                    data.contract_id,
                    data.metakey_id,
                    data.metadata_id,
                    data.metakey_name,
                    data.metadata_value,
                    data.metadate_date_value,
                ])
                count += 1

            logger.info(f"CSVに書き込まれた行数: {count}")

            return response

        except Exception as e:
            # 503エラーが発生した場合、またはその他の予期しないエラー
            logger.error(f"予期しないエラーが発生しました - 500 Error: {str(e)}")
            # エラーメッセージと共に503エラーをクライアントに返す
            return Response({"detail": "後ほど再試行してください。"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SettingContractMetaCSVDownloadView(APIView):
    def get(self, request):
        try:
            start_time = time.perf_counter()
            # ダウンロード処理
            req_serializer = SettingContractMetaDownloadRequestSerializer(data=request.query_params)
            if not req_serializer.is_valid():
                return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Serializerから日付を取得 (datetime-local形式対応)
            create_date_from_str = req_serializer.validated_data['createDateFrom']
            create_date_to_str = req_serializer.validated_data['createDateTo']

            # `from` を 17:45:00.000000, `to` を 17:45:59.999999 に設定
            create_date_from = timezone.make_aware(datetime.datetime.fromisoformat(create_date_from_str).replace(second=0, microsecond=0))
            create_date_to = timezone.make_aware(datetime.datetime.fromisoformat(create_date_to_str).replace(second=59, microsecond=999999))

            step1_time = time.perf_counter()
            logger.info(f"日付変換完了: {step1_time - start_time:.4f}秒")

            status_values = [
                ContractStatusable.Status.UNUSED.value,
                ContractStatusable.Status.USED.value,
                ContractStatusable.Status.SIGNED_BY_PAPER.value,
                ContractStatusable.Status.CANCELED.value,
                ContractStatusable.Status.EXPIRED.value,
            ]

            # メタデータの取得（key_id=1 のデータのみ）
            meta_data_queryset = MetaData.objects.filter(
                key_id=1, status=MetaData.Status.ENABLE.value
            ).select_related("contract")

            # `MetaData` を辞書化
            contract_id_to_meta_data = {
                meta.contract_id: meta for meta in meta_data_queryset
            }

            step2_time = time.perf_counter()
            logger.info(f"メタデータ取得完了: {step2_time - step1_time:.4f}秒")

            # Contractデータを取得（1分間の範囲）
            matching_contracts = Contract.objects.filter(
                is_garbage=False,
                status__in=status_values,
                account=self.request.user.account,
                created_at__range=(create_date_from, create_date_to)
            ).order_by('created_at').select_related("created_by", "directory")

            step3_time = time.perf_counter()
            logger.info(f"契約データ取得完了: {step3_time - step2_time:.4f}秒")

            if not matching_contracts.exists():
                return Response({"msg": ["対象のファイルがありません"]}, status=status.HTTP_200_OK)

            matching_contracts_count = matching_contracts.count()
            logger.info(f"取得したデータ数:{matching_contracts_count}")
            logger.info(f"アカウントid:{self.request.user.account.id}")

            # **ファイル名を取得して辞書化**
            contract_id_to_file_name = dict(
                Contract.objects.filter(id__in=matching_contracts.values_list("id", flat=True))
                .annotate(file_name=Coalesce(F("file__name"), Value("")))
                .values_list("id", "file_name")
            )

            step4_time = time.perf_counter()
            logger.info(f"ファイル名取得完了: {step4_time - step3_time:.4f}秒")

            # CSVファイルをレスポンスとして準備
            response = HttpResponse(content_type='text/csv')
            now = datetime.datetime.now()
            file_name = f'conpass_contract_metadata_{now.strftime("%Y%m%d%H%M%S")}'
            response['Content-Disposition'] = f'attachment; filename="{file_name}.csv"'

            response.write('\ufeff'.encode('utf-8'))

            writer = csv.writer(response, quotechar='"')
            writer.writerow(['契約書ID', '登録日時', '登録者名', 'PDFファイル名', '契約書タイトル', '契約書タイプ', '契約書ステータス', '格納フォルダ名', 'フォルダ種別'])

            # 契約ステータスのマッピング
            status_map = {
                ContractStatusable.Status.UNUSED.value: "未採用",
                ContractStatusable.Status.USED.value: "採用済",
                ContractStatusable.Status.SIGNED_BY_PAPER.value: "締結済",
                ContractStatusable.Status.CANCELED.value: "解約",
                ContractStatusable.Status.EXPIRED.value: "契約満了"
            }

            step5_time = time.perf_counter()
            logger.info(f"CSVヘッダー作成完了: {step5_time - step4_time:.4f}秒")

            # 取得したデータをCSVに書き込む
            for contract in matching_contracts:
                # 契約書タイトルの抽出
                meta_data = contract_id_to_meta_data.get(contract.id)
                contract_title = meta_data.value if meta_data else ''

                # 契約書タイプ
                contract_type = "契約書" if contract.type == ContractTypeable.ContractType.CONTRACT.value else "契約書テンプレート"

                # 契約書ステータスの取得
                status_type = status_map.get(contract.status, "不明")

                # 親フォルダ判定
                directory_level = "親" if contract.directory.level == 0 else "子"

                # 時間のフォーマット
                formatted_created_at = timezone.localtime(contract.created_at).strftime('%Y-%m-%d %H:%M')

                # PDFファイル名（辞書から取得）
                file_name = contract_id_to_file_name.get(contract.id, '')

                writer.writerow([
                    contract.id,
                    formatted_created_at,
                    contract.created_by,
                    file_name,
                    contract_title,
                    contract_type,
                    status_type,
                    contract.directory,
                    directory_level,
                ])

            step6_time = time.perf_counter()
            logger.info(f"CSVデータ作成完了: {step6_time - step5_time:.4f}秒")

            return response

        except Exception as e:
            logger.error(f"予期しないエラーが発生しました - 500 Error: {str(e)}")
            return Response({"detail": "後ほど再試行してください。"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SettingMetaDirectoryView(APIView):
    """
    階層単位メタ情報取得
    """

    def get(self, request):
        params = request.query_params
        directory = Directory.objects.filter(parent__isnull=True,
                                             type=params.get('type'),
                                             account_id=self.request.user.account_id,
                                             status=MetaKey.Status.ENABLE.value).all()
        res = SettingDirectoryResponseBodySerializer(directory)
        return Response(data=res.data)


class DirectoryMetaView(APIView):
    """
    階層単位メタ情報取得
    """

    def get(self, request):
        params = request.query_params
        meta_key = MetaKey.objects.filter(Q(status=MetaKey.Status.ENABLE.value), Q(type=MetaKey.Type.DEFAULT.value) | Q(
            account_id=self.request.user.account_id)).all() \
            .prefetch_related(Prefetch('meta_key_directory_key',
                                       queryset=MetaKeyDirectory.objects.filter(directory_id=params.get('id'), account_id=request.user.account)
                                       .all()))
        default_list = []
        free_list = []
        default_visible = True
        for data in meta_key:
            meta_key_directory = data.meta_key_directory_key.all()
            if data.type != MetaKey.Type.DEFAULT.value:
                default_visible = False
            row = {
                'id': data.id,
                'name': data.name,
                'type': data.type,
                'is_visible': meta_key_directory[0].is_visible if meta_key_directory else default_visible,
                'meta_key_directory_id': meta_key_directory[0].id if meta_key_directory else None,
            }
            if data.type == MetaKey.Type.DEFAULT.value:
                default_list.append(row)
            else:
                free_list.append(row)

        data = {
            'default_list': list(default_list),
            'free_list': list(free_list),
        }

        res = SettingDirectoryMetaResponseBodySerializer(data)
        return Response(data=res.data)


class DirectoryMetaUpdateView(APIView):
    """
    階層単位メタ情報取得・更新
    """
    @transaction.atomic
    def post(self, request):
        serializer = SettingDirectoryMetaRequestBodySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        directory_id = serializer.validated_data['directoryId']
        now = timezone.now()

        # ──────────────── MetaKey 存在チェック ────────────────
        # defaultList / freeList 両方から key_id を集める
        all_ids = []
        for list_name in ('defaultList', 'freeList'):
            for item in serializer.validated_data.get(list_name, []):
                all_ids.append(item['id'])
        unique_ids = set(all_ids)

        # DB から該当する MetaKey を取得
        existing_ids = set(
            MetaKey.objects.filter(
                Q(id__in=unique_ids),
                Q(status=Statusable.Status.ENABLE.value),
                (Q(account_id=user.account_id) | Q(account_id__isnull=True))
            )
            .values_list('id', flat=True)
        )
        # もしリクエストに含まれる id と一致しないものがあれば不正とみなす
        missing = unique_ids - existing_ids
        if missing:
            logger.info(f"Invalid MetaKey IDs: {missing}")
            return Response(
                {"msg": ["パラメータが不正です....."]},
                status=status.HTTP_400_BAD_REQUEST
            )
        # ──────────────── ここまで MetaKey 存在チェック ────────────────

        try:
            for list_name in ('defaultList', 'freeList'):
                for data in serializer.validated_data.get(list_name, []):
                    key_id = data['id']
                    is_visible = data['is_visible']

                    # ─── 作成時 only の defaults を指定 ───
                    mqd, created = MetaKeyDirectory.objects.get_or_create(
                        key_id=key_id,
                        directory_id=directory_id,
                        account_id=user.account_id,
                        defaults={
                            'is_visible': is_visible,
                            'created_by_id': user.id,
                            'created_at': now,
                            'status': Statusable.Status.ENABLE.value,
                            'updated_by_id': user.id,
                            'updated_at': now,
                        }
                    )

                    if not created:
                        mqd.is_visible = is_visible
                        mqd.updated_by_id = user.id
                        mqd.updated_at = now
                        mqd.save(update_fields=[
                            'is_visible',
                            'updated_by_id',
                            'updated_at',
                        ])

        except MetaKeyDirectory.DoesNotExist as e:
            # get() 部分で想定外のパラメータ不正があった場合
            logger.info(e)
            return Response(
                {"msg": ["パラメータが不正です"]},
                status=status.HTTP_400_BAD_REQUEST
            )

        except DatabaseError as e:
            # 一般的な DB エラー
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response(
                {"msg": ["DBエラーが発生しました"]},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({"msg": ["登録しました"]}, status=status.HTTP_200_OK)
