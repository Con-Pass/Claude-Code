import traceback
from logging import getLogger

from django.db.models import Prefetch
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.views import APIView

from conpass.models import File, Contract, FileUploadStatus, Permission, PermissionTarget
from conpass.services.paginate.paginate import StandardResultsSetPagination
from conpass.views.file.serializer.file_serializer import FileRequestBodySerializer, FileResponseBodySerializer, \
    FileLinkedContractRequestBodySerializer, FileListSerializer, FileUploadStatusListSerializer, \
    LinkedFileDeleteRequestBodySerializer
from conpass.services.directory.directory_service import DirectoryService
from conpass.models.constants.contracttypeable import ContractTypeable
from conpass.models.constants import Statusable
import datetime
from django.utils.timezone import make_aware

logger = getLogger(__name__)


class FileListView(generics.ListAPIView):
    """
    Account情報に紐づくアップロード済ファイル一覧を返す
    GCSの方は見に行かず、DBの情報を返します
    """
    serializer_class = FileListSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = File.objects.filter(
            status=File.Status.ENABLE.value,
            account=self.request.user.account_id
        )
        if name := self.request.GET.get('name'):
            queryset = queryset.filter(name__contains=name)

        queryset = queryset.order_by('id')
        return queryset


class FileLinkedContractListView(APIView):
    """
    契約書に紐づく関連ファイル一覧を返す
    GCSの方は見に行かず、DBの情報を返します
    契約書自体のファイル（File.type=CONTRACTやTEMPLATE）も含む
    """

    def get(self, request):
        # request
        req_serializer = FileLinkedContractRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        contract_wheres = {
            'id': req_serializer.data.get('contractId'),
            'account': request.user.account_id
        }
        try:
            contract = Contract.objects.exclude(
                status=Contract.Status.DISABLE.value).filter(**contract_wheres)\
                .prefetch_related(Prefetch('file', queryset=File.objects.filter(status=File.Status.ENABLE.value).order_by('type').all()))
            files = contract.get().get_files({})  # ファイルはない場合もある
        except Contract.DoesNotExist as e:
            logger.info(e)
            return Response("契約書が見つかりません", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response("エラーが発生しました", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # response
        response = {
            'total': len(files),
            'files': files,
        }

        res_serializer = FileResponseBodySerializer(response)
        return Response(data=res_serializer.data)


class FileStrageView(APIView):
    """
    指定の日時に一番近いデータ
    """
    pass


class CustomResultsSetPagination(StandardResultsSetPagination):
    """
    ページサイズの設定
    """
    page_size = 100  # 1ページあたりの表示件数を100件に設定


class FileUploadStatusListView(generics.ListAPIView):
    """
    アップロード履歴の一覧を返す
    レコードの抽出単位は、ユーザーのフォルダの権限単位
    """
    serializer_class = FileUploadStatusListSerializer
    pagination_class = CustomResultsSetPagination

    def get_queryset(self):
        # 閲覧権限のあるフォルダのみ
        directoryService = DirectoryService()
        allowed_contract_dirs = \
            directoryService.get_allowed_directories(self.request.user, ContractTypeable.ContractType.CONTRACT.value)
        allowed_template_dirs = \
            directoryService.get_allowed_directories(self.request.user, ContractTypeable.ContractType.TEMPLATE.value)
        allowed_past_dirs = \
            directoryService.get_allowed_directories(self.request.user, ContractTypeable.ContractType.PAST.value)
        allowed_directory_ids = [directory.id for directory in allowed_contract_dirs] \
            + [directory.id for directory in allowed_template_dirs] \
            + [directory.id for directory in allowed_past_dirs] \

        queryset = FileUploadStatus.objects.filter(
            status=File.Status.ENABLE.value,
            account=self.request.user.account_id,
            directory__id__in=allowed_directory_ids,
        )

        queryset = queryset.order_by('-upload_datetime')
        return queryset


class FileLinkedContractDeleteView(APIView):
    """
    紐付けされたファイルの論理削除
    app/conpass/views/gcp/cloud_storage.pyのGoogleCloudStorageFileLinkedContractDeleteViewに
    GCS上のファイルを削除するバージョンあり
    """
    def post(self, request):
        req_serializer = LinkedFileDeleteRequestBodySerializer(data=request.data)
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

        return Response("該当のファイルを削除しました。", status=status.HTTP_200_OK)
