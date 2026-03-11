import copy
import csv
import difflib
import itertools
import os
import datetime
import time
import base64
import re
import tempfile
import traceback
import urllib.parse
import zipfile
from urllib.parse import unquote
import math
import html
from logging import getLogger
from operator import or_
from functools import reduce
from collections import OrderedDict
from django.conf import settings
from django.http import HttpResponse
from django.db.models import Q, F, Prefetch, Exists, OuterRef, Subquery, Case, When, Value, BooleanField, DateField
from django.db.models.functions import Coalesce
from django.db.utils import DatabaseError
from django.db import transaction
from django.utils import timezone
from django.utils.timezone import make_aware
from dateutil.relativedelta import relativedelta
from rest_framework import generics, status, serializers
from rest_framework.generics import get_object_or_404, ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.parsers import FormParser, MultiPartParser

from bs4 import BeautifulSoup

from conpass.models import AdobeSign, Workflow
from conpass.models.company_meta_key import CompanyMetaKey
from conpass.models.constants.contractstatusable import ContractStatusable
from conpass.services.contract.contract_enum import AIAgentNotifyEnum
from conpass.services.directory.directory_service import DirectoryService
from conpass.services.paginate.paginate import StandardResultsSetPagination
from conpass.services.contract.contract_service import ContractService, META_INFO_DATE
from conpass.views.contract.serializer.contract_body_serializer import ContractBodyItemResponseBodySerializer, \
    ContractBodyItemRequestBodySerializer, ContractBodyListRequestBodySerializer, \
    ContractBodyListResponseBodySerializer, \
    ContractBodyVersionAdoptRequestSerializer, ContractBodyDiffHtmlRequestBodySerializer, \
    ContractBodyDiffHtmlResponseSerializer
from conpass.views.contract.serializer.contract_data_list_serializer import ContractDataListRequestBodySerializer, \
    ContractDataListResponseBodySerializer
from conpass.views.contract.serializer.contract_item_serializer import ContractItemRequestBodySerializer, \
    ContractItemResponseBodySerializer, ContractMetaDataResponseBodySerializer, \
    ContractMetaDataListRequestBodySerializer, \
    ContractChildsResponseBodySerializer, ContractChildsRequestBodySerializer
from conpass.views.contract.serializer.contract_list_serializer import ContractListRequestBodySerializer, \
    ContractListResponseSerializer
from conpass.views.contract.serializer.contract_archive_create_serializer \
    import ContractArchiveCreateRequestBodySerializer
from conpass.views.contract.serializer.contract_archive_list_serializer \
    import ContractArchiveListRequestBodySerializer, ContractArchiveListResponseSerializer
from conpass.views.contract.serializer.contract_archive_recent_serializer \
    import ContractArchiveRecentRequestBodySerializer, ContractArchiveRecentResponseBodySerializer
from conpass.views.contract.serializer.contract_archive_delete_serializer import ContractArchiveDeleteRequestBodySerializer
from conpass.views.contract.serializer.contract_dashboard_notify_serializer import \
    ContractRenewalListResponseBodySerializer, ContractWithMetaRequestBodySerializer
from conpass.views.contract.serializer.contract_open_serializer import ContractOpenRequestBodySerializer
from conpass.views.contract.serializer.contract_related_serializer import ContractBriefInfoSerializer
from conpass.views.contract.serializer.contract_zip_download_serializer import ContractZipDownloadRequestBodySerializer
from conpass.views.contract.serializer.contract_search_setting_serializer \
    import ContractSearchSettingRequestBodySerializer, \
    ContractSearchSettingEditRequestBodySerializer, ContractSearchSettingResponseBodySerializer
from conpass.views.contract.serializer.contract_directory_update_serializer \
    import ContractDirectoryUpdateRequestBodySerializer
from conpass.views.contract.serializer.contract_directory_list_serializer \
    import ContractDirectoryListRequestBodySerializer, ContractDirectoryListResponseBodySerializer
from conpass.views.contract.serializer.contract_garbage_update_serializer \
    import ContractGarbageUpdateRequestBodySerializer
from conpass.views.contract.serializer.contract_status_update_serializer \
    import ContractStatusUpdateRequestBodySerializer
from conpass.views.contract.serializer.contract_comment_serializer import ContractCommentRequestBodySerializer, \
    ContractCommentDeleteRequestBodySerializer, ContractMentionRequestBodySerializer
from conpass.views.contract.serializer.contract_meta_key_list_serializer import ContractMetaKeyListResponseBodySerializer
from conpass.models import Contract, ContractBody, ContractComment, User, MetaData, MetaKey, ContractArchive, Directory, \
    File, ContractCommentMention
from conpass.models.constants.contracttypeable import ContractTypeable
from conpass.models.constants.contractmetakeyidable import ContractMetaKeyIdable
from conpass.services.gcp.cloud_storage import GoogleCloudStorage, GCSBucketName
from conpass.mailer.mention_mailer import MentionMailer
from conpass.views.dashboard.serializer.dashboard_renew_notify_serializer import UpdateContractRenewNotifySerializer
from conpass.models.constants import Statusable
from conpass.services.contract.metadata_csv_importer import MetaDataCsvImporter
from conpass.services.contract.tasks import  notify_to_AI_agent

logger = getLogger(__name__)

COOKIE_NAME = 'contract-search-setting'
COOKIE_NAME_TEMPLATE = 'contract-template-search-setting'
COOKIE_NAME_BULK = 'contract-bulk-search-setting'
RECENT_ARCHIVE_NUM = 2


class ListView(APIView):
    def get(self, request):
        # request
        req_serializer = ContractListRequestBodySerializer(data=self.request.query_params)
        req_serializer.is_valid(raise_exception=True)

        service = ContractService()
        query = service.query_search(user=self.request.user, params=req_serializer.data)

        serializer = ContractListResponseSerializer(query.all(), many=True)
        return Response(data=serializer.data)


class PaginateView(generics.ListAPIView):
    serializer_class = ContractListResponseSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        # request
        req_serializer = ContractListRequestBodySerializer(data=self.request.query_params)
        req_serializer.is_valid(raise_exception=True)

        service = ContractService()

        return service.query_search(user=self.request.user, params=req_serializer.data)

    def get_page_size(self, request):
        # Cookieから設定を取得
        setting_cookie = request.COOKIES.get(COOKIE_NAME, '')
        # デフォルトのpage_sizeを設定ファイルから取得
        default_page_size = settings.REST_FRAMEWORK['PAGE_SIZE']
        # page_sizeの初期値をデフォルト値に設定
        page_size = default_page_size

        setting_list = setting_cookie.split('&')
        for item in setting_list:
            parts = item.split(':')
            if len(parts) == 2:
                key, value = parts
                if key == 'pageSize' and value.isdigit():
                    page_size = int(value)
                    break

        return page_size

    def paginate_queryset(self, queryset):
        """
        クエリセットのページネーションを行い、ページサイズをリクエストから取得して設定する。
        """
        self.paginator.page_size = self.get_page_size(self.request)
        return super().paginate_queryset(queryset)


class ItemView(APIView):

    def get(self, request):
        # request
        req_serializer = ContractItemRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        id = req_serializer.data.get('id')

        # query
        type_param = req_serializer.data.get('type')
        contract_type = None
        if type_param == ContractTypeable.ContractType.CONTRACT.value:
            contract_type = ContractTypeable.ContractType.CONTRACT.value
        elif type_param == ContractTypeable.ContractType.TEMPLATE.value:
            contract_type = ContractTypeable.ContractType.TEMPLATE.value

        wheres = {
            'pk': id,
            'type': contract_type,
            'account': self.request.user.account
        }
        excludes = {
            'status': Contract.Status.DISABLE.value
        }
        try:
            contract = Contract.objects.filter(**wheres).exclude(**excludes) \
                .select_related('account', 'client', 'directory', 'template') \
                .get()
        except Contract.DoesNotExist as e:
            logger.info(e)
            return Response("契約書が見つかりません", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
            return Response("エラーが発生しました", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        directory_service = DirectoryService()
        visible_directories = directory_service.get_allowed_directories(self.request.user, contract_type)
        if contract.directory not in visible_directories:
            contract = Contract()
            contract.id = 0
        try:
            res_serializer = ContractItemResponseBodySerializer(contract)
        except Exception as e:
            logger.info(e)
        return Response(data=res_serializer.data)

    def post(self, request):
        # request
        req_serializer = ContractItemRequestBodySerializer(data=request.data["params"])
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        type_param = req_serializer.data.get('type')
        contract_type = None
        if type_param == ContractTypeable.ContractType.CONTRACT.value:
            contract_type = ContractTypeable.ContractType.CONTRACT.value
        elif type_param == ContractTypeable.ContractType.TEMPLATE.value:
            contract_type = ContractTypeable.ContractType.TEMPLATE.value
        directory_id = req_serializer.data.get('directory_id')

        now = make_aware(datetime.datetime.now())
        user = self.request.user
        contract = self.create_contract(now, user, contract_type, directory_id)

        # response
        res_serializer = ContractItemResponseBodySerializer(contract)
        return Response(data=res_serializer.data)

    def create_contract(self, now, user, contract_type, directory_id):
        contract = Contract()
        contract.status = Contract.Status.UNUSED.value \
            if contract_type == ContractTypeable.ContractType.TEMPLATE.value else Contract.Status.ENABLE.value
        contract.account = user.account
        contract.type = contract_type
        contract.directory_id = directory_id
        contract.created_at = now
        contract.created_by = user
        contract.updated_at = now
        contract.updated_by = user
        contract.save()
        if contract.type == ContractTypeable.ContractType.TEMPLATE.value:
            contract.template_id = contract.id  # 自分自身
        contract.origin_id = contract.id  # 自分自身
        contract.save()

        contract_body = ContractBody()
        contract_body.contract = contract
        contract_body.status = ContractBody.Status.ENABLE.value
        contract_body.created_at = now
        contract_body.created_by = user
        contract_body.updated_at = now
        contract_body.updated_by = user
        if contract_type == ContractTypeable.ContractType.TEMPLATE.value:
            contract_body.is_adopted = True
        else:
            contract_body.is_adopted = False
        contract_body.version = "1.0"
        contract_body.save()

        # 全検索用モデルとMeilisearchに保存
        try:
            contract_service = ContractService()
            contract_service.save_contract_body_search_task(contract_body, now)
        except Exception as e:
            logger.error(f"contract_body_search error:{e}")

        return contract


class ContractChildsView(APIView):

    def get(self, request):
        # request
        req_serializer = ContractChildsRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # query
        parent_id = req_serializer.data.get('parentId')

        wheres = {
            'parent_id': parent_id,
            'account': self.request.user.account
        }
        excludes = {
            'status': Contract.Status.DISABLE.value
        }
        try:
            contracts = list(Contract.objects.filter(**wheres).exclude(**excludes).select_related('account', 'client',
                                                                                                  'directory',
                                                                                                  'template').all())
        except Contract.DoesNotExist as e:
            logger.info(e)
            return Response("契約書が見つかりません", status=status.HTTP_400_BAD_REQUEST)

        # response
        res_serializer = ContractChildsResponseBodySerializer(contracts)
        return Response(data=res_serializer.data)


class ContractCommentView(APIView):

    def post(self, request):
        # request
        req_serializer = ContractCommentRequestBodySerializer(data=request.data["params"])
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        id = req_serializer.data.get('id')
        version = req_serializer.data.get('version')
        comment = req_serializer.data.get('comment')
        decoded_comment = base64.b64decode(urllib.parse.unquote(comment)).decode()
        user_id = self.request.user.id

        # query
        try:
            contractservice = ContractService()
            if contractservice.is_allow_to_user(id, self.request.user):
                contractservice.save_comment(id, version, decoded_comment, user_id)
            else:
                return Response("契約書が見つかりません。", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(e)
            return Response("コメントの保存に失敗しました", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # response
        return Response("OK", status=status.HTTP_200_OK)


class ContractCommentDeleteView(APIView):

    def post(self, request):
        # request
        req_serializer = ContractCommentDeleteRequestBodySerializer(data=request.data["params"])
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        contract_id = req_serializer.data.get('contractId')
        comment_id = req_serializer.data.get('commentId')
        user_id = self.request.user.id
        # query
        try:
            contractservice = ContractService()
            if contractservice.is_allow_to_user(contract_id, self.request.user):
                contractservice.delete_comment(comment_id, user_id)
            else:
                return Response("契約書が見つかりません。", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(e)
            return Response("コメントの削除に失敗しました", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # response
        return Response("OK", status=status.HTTP_200_OK)


class ContractMentionView(APIView):

    def __init__(self):
        self.mention_mailer = MentionMailer()

    def post(self, request):
        try:
            req_serializer = ContractMentionRequestBodySerializer(data=request.data["params"])
            if not req_serializer.is_valid():
                return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            id = req_serializer.data.get('id')  # 契約書ID
            version = req_serializer.data.get('version')
            comment = req_serializer.data.get('comment')
            decoded_comment = base64.b64decode(unquote(comment)).decode()
            user_id = request.user.id  # コメント作成者
            user_name = request.user
            account_id = request.user.account_id

            comment_str = unquote(decoded_comment)

            # 以降の処理をトランザクションとして管理
            with transaction.atomic():
                contract = self.get_contract(id, account_id)
                if not contract:
                    return Response("契約書が見つかりません。", status=status.HTTP_400_BAD_REQUEST)

                contract_url = self.construct_contract_url(contract)
                users = req_serializer.data.get('users')

                self.save_comment(id, version, decoded_comment, user_id, request.user, users, account_id)

                if users:
                    self.send_mention_emails(users, account_id, comment_str, version, contract_url, user_name, contract)

                return Response("OK", status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(e)
            return Response("エラーが発生しました。", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_contract(self, id, account_id):
        excludes = {
            'status': Contract.Status.DISABLE.value
        }
        contract = Contract.objects.filter(pk=id, account=account_id).exclude(**excludes).first()
        return contract

    def construct_contract_url(self, contract):
        if contract.type == ContractTypeable.ContractType.CONTRACT.value:
            return f"https://www.con-pass.jp/contract/{contract.id}"
        elif contract.type == ContractTypeable.ContractType.TEMPLATE.value:
            return f"https://www.con-pass.jp/contract/template/{contract.id}"

    def save_comment(self, id, version, comment, user_id, user, users, account_id):
        contractservice = ContractService()
        if not contractservice.is_allow_to_user(id, user):
            raise Exception("ユーザーには契約書へのアクセス権限がありません。")
        comment_id = contractservice.save_comment(id, version, comment, user_id)
        now = make_aware(datetime.datetime.now())
        if users:
            self.mention_user_post(users, account_id, comment_id, user_id, now)

    def send_mention_emails(self, users, account_id, comment_str, version, contract_url, user_name, contract):
        id_list = [odict['id'] for odict in users]
        wheres = {
            'account_id': account_id,
            'status': User.Status.ENABLE.value,
            'type': User.Type.ACCOUNT.value,
            'is_bpo': False,
            'id__in': id_list if id_list else None
        }
        user_list_filter = User.objects.filter(**wheres).all()
        for user in user_list_filter:
            self.mention_mailer.send_mention_mail(user, comment_str, version, contract_url, user_name, contract.name, contract.directory, contract.client)

    def mention_user_post(self, users, account_id, comment_id, user_id, now):
        id_list = [odict['id'] for odict in users]
        wheres = {
            'account_id': account_id,
            'status': User.Status.ENABLE.value,
            'type': User.Type.ACCOUNT.value,
            'is_bpo': False,
            'id__in': id_list if id_list else None
        }
        user_list_filter = User.objects.filter(**wheres).all()
        for mention_user in user_list_filter:
            # 新しいContractCommentMentionインスタンスを作成
            contractCommentMention = ContractCommentMention(
                comment_id=comment_id,  # コメントID
                user_id=mention_user.id,  # メンションされたユーザーID
                created_at=now,  # 作成日時
                created_by_id=user_id,  # 作成者ID
                updated_at=now,  # 更新日時
                updated_by_id=user_id  # 更新者ID
            )
            # データベースに保存
            contractCommentMention.save()


class BodyView(APIView):
    """
    １つの契約書に紐づく本文（contract_body）を取得する
    本文は複数紐づくはずだが、最新の１件でよい
    id : 契約書ID
    """

    def get(self, request):
        # request
        req_serializer = ContractBodyItemRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        contract_id = req_serializer.data.get('id')
        version = req_serializer.data.get('version')
        account_id = self.request.user.account_id

        # contractのaccount 確認
        contract_wheres = {
            'id': contract_id,
            'account_id': account_id
        }
        contract_excludes = {
            'status': Contract.Status.DISABLE.value
        }
        if not Contract.objects.filter(**contract_wheres).exclude(**contract_excludes).count() > 0:
            return Response("契約書が見つかりません", status=status.HTTP_400_BAD_REQUEST)

        # query
        wheres = {
            'status': ContractBody.Status.ENABLE.value,
            'contract_id': contract_id,
        }
        if version:
            wheres['version'] = version
        try:
            contract_body = ContractBody.objects.filter(**wheres).latest('updated_at')
        except ContractBody.DoesNotExist as e:
            logger.info(e)
            return Response("契約書が見つかりません", status=status.HTTP_400_BAD_REQUEST)

        # response
        res_serializer = ContractBodyItemResponseBodySerializer(contract_body)
        return Response(data=res_serializer.data)


class BodySaveView(APIView):
    """
    １つの契約書に紐づく本文を保存する
    更新ではなく、新しいレコードを作る
    contract自体もupdatedを更新する
    id : 契約書ID
    text: 本文
    """

    def post(self, request):
        # request
        req_serializer = ContractBodyItemRequestBodySerializer(data=request.data["params"])
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        id = req_serializer.data.get('id')
        version = req_serializer.data.get('version')
        body = req_serializer.data.get('body') or ""
        decoded_body = base64.b64decode(urllib.parse.unquote(body)).decode()
        is_provider = req_serializer.data.get('isProvider')
        user_id = self.request.user.id

        # query
        try:
            contractservice = ContractService()
            if contractservice.is_allow_to_user(id, self.request.user):
                contractservice.save_body(id, version, decoded_body, is_provider, user_id)
                notify_to_AI_agent.delay([id], AIAgentNotifyEnum.UPDATED.value)
            else:
                return Response("契約書が見つかりません。", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(e)
            return Response("契約書本文の保存に失敗しました", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # response
        return Response("OK", status=status.HTTP_200_OK)


class ContractBodyListView(APIView):

    def get(self, request):
        """
        契約書本文の一覧を取得
        """
        req_serializer = ContractBodyListRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        wheres = {
            'contract_id': req_serializer.data.get('id'),
            'status': ContractBody.Status.ENABLE.value
        }
        contract_body_list = list(ContractBody.objects.filter(**wheres).order_by('updated_at').all()
                                  .prefetch_related(Prefetch('contract',
                                                             queryset=Contract.objects
                                                             .exclude(status=User.Status.DISABLE.value)
                                                             .filter(account=self.request.user.account).all())))

        results = self._make_contract_body_diff(contract_body_list)
        res_serializer = ContractBodyListResponseBodySerializer(results)
        return Response(data=res_serializer.data)

    def _make_contract_body_diff(self, contract_body_list: [ContractBody]):
        """
        contract_body.body の履歴から diff を作成し、レスポンス用データを作る
        利用者側に表示する内容になるので、現状は概要的な扱いです
        → 削除、追加した部分だけを抽出して、全文は含めない
        """
        results = []
        pre_body = [""]
        for contract_body in contract_body_list:
            now_body = urllib.parse.unquote(contract_body.body).split("\n")
            diffs = []
            for d in difflib.ndiff(pre_body, now_body):
                if d[0:1] in ['+', '-'] and len(d) > 2 and not ("&nbsp;" in d):
                    d = re.sub(r'^\-', '（削除）', d)
                    d = re.sub(r'^\+', '（追加）', d)
                    diffs.append(d)
            result = {
                'diff': urllib.parse.quote("\n".join(diffs)),
                'body': contract_body
            }
            pre_body = now_body
            results.append(result)
        results.reverse()  # 新しい順にする
        return results


class ContractBodyDiffHtmlView(APIView):

    def get(self, request):
        """
        IDと比較する2つのバージョンを受け取りbodyのdiffをhtml形式で返す
        """
        req_serializer = ContractBodyDiffHtmlRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        contract_id = req_serializer.data.get('id')
        older_version = req_serializer.data.get('olderVersion')
        newer_version = req_serializer.data.get('newerVersion')
        account_id = self.request.user.account_id

        # contractのaccount 確認
        contract_wheres = {
            'id': contract_id,
            'account_id': account_id
        }
        contract_excludes = {
            'status': Contract.Status.DISABLE.value
        }
        if not Contract.objects.filter(**contract_wheres).exclude(**contract_excludes).count() > 0:
            return Response("契約書が見つかりません", status=status.HTTP_400_BAD_REQUEST)

        # query
        wheres_to_old = {
            'status': ContractBody.Status.ENABLE.value,
            'contract_id': contract_id,
            'version': older_version,
        }
        wheres_to_new = {
            'status': ContractBody.Status.ENABLE.value,
            'contract_id': contract_id,
            'version': newer_version,
        }

        try:
            older_contract_body = ContractBody.objects.filter(**wheres_to_old).latest('updated_at')
            newer_contract_body = ContractBody.objects.filter(**wheres_to_new).latest('updated_at')
        except ContractBody.DoesNotExist as e:
            logger.info(e)
            return Response("契約書が見つかりません", status=status.HTTP_400_BAD_REQUEST)

        def convert_text(body):
            # URLデコード
            url_decoded_body = urllib.parse.unquote(body)
            # HTMLエンティティを通常の文字に変換し、改行と特殊文字を除去
            converted_body = html.unescape(url_decoded_body).replace('\n', '').replace("\xa0", " ")
            # 分割してリスト化
            decoded_body = converted_body.split("</p>")
            result = []
            for expression_decoded_body in decoded_body:
                result.append(BeautifulSoup(expression_decoded_body, "lxml").text)
            return result

        older_body = convert_text(older_contract_body.body)
        newer_body = convert_text(newer_contract_body.body)

        result = difflib.HtmlDiff().make_table(older_body, newer_body)
        res_serializer = ContractBodyDiffHtmlResponseSerializer({"diffData": result})
        return Response(data=res_serializer.data)


class ContractBodyVersionAdoptView(APIView):

    def post(self, request):
        """
        一度全ての採用フラグを0にしたのち
        選択したバージョンに採用フラグを立てる
        """
        # request
        req_serializer = ContractBodyVersionAdoptRequestSerializer(data=request.data["params"])
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        id = req_serializer.data.get('id')
        version = req_serializer.data.get('version')
        user_id = self.request.user.id

        # query
        try:
            contractservice = ContractService()
            if contractservice.is_allow_to_user(id, self.request.user):
                contractservice.adopt_version(id, version, user_id)
            else:
                return Response("契約書が見つかりません。", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(e)
            return Response("本バージョンの採用に失敗しました", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # response
        return Response("OK", status=status.HTTP_200_OK)


class ContractMetaDataListView(APIView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.contract_service = ContractService()

    def get(self, request, contract_id: int):
        """
        契約書に紐づくメタ情報を取得する
        メタ情報設定で表示設定されている項目のみ表示する。
        全体の表示設定と階層単位の表示設定はAND条件とする。
        """
        user=request.user
        account= request.user.account
        try:
            contract = Contract.objects.exclude(
                status=Contract.Status.DISABLE.value
            ).get(
                pk=contract_id,
                account=self.request.user.account
            )
        except Contract.DoesNotExist as e:
            logger.info(e)
            return Response("契約書が見つかりません", status=status.HTTP_400_BAD_REQUEST)

        # ルートディレクトリのメタ情報表示設定を使う
        root_directory = self.contract_service.get_root_directory(contract)
        if root_directory:
            default_key_ids = [key.id for key in root_directory.keys.filter(
                is_visible=True,
                meta_key_directory_key__is_visible=True,
                type= MetaKey.Type.DEFAULT.value
            ).all()]
            invisible_default_key_ids=list(CompanyMetaKey.objects.filter(account=account, is_visible=False, meta_key_id__in=default_key_ids).values_list('meta_key', flat=True))
            visible_default_key_ids= list(filter(lambda x: x not in invisible_default_key_ids, default_key_ids))
            free_key_ids = [key.id for key in root_directory.keys.filter(
                is_visible=True,
                meta_key_directory_key__is_visible=True,
                type= MetaKey.Type.FREE.value
            ).all()]

            visible_key_ids=visible_default_key_ids+free_key_ids


        else:
            visible_key_ids = []

        # デフォルト項目
        metadata_default = MetaData.objects.select_related("key").filter(
            contract_id=contract.id,
            status=MetaData.Status.ENABLE.value,
            key__type=MetaKey.Type.DEFAULT.value,
            key__status=MetaKey.Status.ENABLE.value,
            key__id__in=visible_key_ids,
        ).order_by('-key__type', 'key_id', 'value').all()
        inputted_default_key_ids = [default.key_id for default in metadata_default]

        # "担当者名" のデフォルト項目を1つにまとめる
        metadata_default_combined = []
        grouped_meta_data = {}
        for meta_data in metadata_default:
            if meta_data.key.name == "担当者名":
                # "担当者名" をまとめる
                if meta_data.key.id not in grouped_meta_data:
                    grouped_meta_data[meta_data.key.id] = meta_data
                    grouped_meta_data[meta_data.key.id].value = meta_data.value
                else:
                    grouped_meta_data[meta_data.key.id].value += f",{meta_data.value}"
            else:
                metadata_default_combined.append(meta_data)
        metadata_default_combined.extend(grouped_meta_data.values())

        # 入力済み自由項目
        metadata_free = MetaData.objects.select_related("key").filter(
            contract_id=contract.id,
            status=MetaData.Status.ENABLE.value,
            key__type=MetaKey.Type.FREE.value,
            key__status=MetaKey.Status.ENABLE.value,
            key__id__in=visible_key_ids,
        ).order_by('-key__type', 'key_id').all()
        inputted_free_key_ids = [free.key_id for free in metadata_free]

        # 未入力自由項目(DBに存在しないデータのためIDなし)
        no_used_meta_keys = MetaKey.objects.filter(
            Q(account_id=self.request.user.account_id) | Q(account_id__isnull=True),
        ).filter(
            status=MetaKey.Status.ENABLE.value,
            id__in=visible_key_ids,
        ).exclude(
            id__in=inputted_default_key_ids + inputted_free_key_ids,
        ).order_by('id').all()
        metadata_no_used_meta_key = [
            MetaData(
                key=meta_key,
            )
            for meta_key in no_used_meta_keys
        ]

        # response
        metadata = itertools.chain(metadata_default_combined, metadata_free, metadata_no_used_meta_key)
        sorted_metadata = sorted(metadata, key=lambda m: m.key_id)
        res_serializer = ContractMetaDataResponseBodySerializer(sorted_metadata)
        return Response(data=res_serializer.data)

    def put(self, request, contract_id: int):
        req_serializer = ContractMetaDataListRequestBodySerializer(data=request.data['params'])
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        result = []
        now = make_aware(datetime.datetime.now())
        for req_data in req_serializer.validated_data['list']:
            if req_data.get('id'):
                # IDがある場合は更新
                try:
                    metadata = self._update_metadata(req_data, contract_id, now)
                except MetaData.DoesNotExist as e:
                    logger.info(e)
                    return Response({'msg': 'パラメータが不正です'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                # IDがない場合はレコード追加
                try:
                    metadata = self._create_metadata(req_data, contract_id, now)
                except MetaKey.DoesNotExist as e:
                    logger.info(e)
                    return Response({'msg': 'パラメータが不正です'}, status=status.HTTP_400_BAD_REQUEST)

            # 修正したメタ情報が契約書名の場合、contract.nameも更新する
            if metadata.key.label == 'title':
                self._update_contract_name(request, metadata, contract_id, now)

            result.append(metadata)
        notify_to_AI_agent.delay([contract_id], AIAgentNotifyEnum.UPDATED.value)
        res_serializer = ContractMetaDataResponseBodySerializer(result)
        return Response(data=res_serializer.data)

    def _update_contract_name(self, request, metadata, contract_id, now):
        try:
            contract = Contract.objects.get(pk=contract_id, account=request.user.account)
            contract.name = metadata.value
            contract.updated_at = now
            contract.updated_by = request.user
            contract.save()
        except Contract.DoesNotExist as e:
            logger.info(e)

    def _update_metadata(self, req_data, contract_id, now):
        metadata = MetaData.objects.filter(
            pk=req_data.get('id'),
            contract_id=contract_id,
            status=MetaData.Status.ENABLE.value
        ).get()

        if metadata.key.label == 'conpass_person':
            if 'value' in req_data and not metadata.lock:
                self._update_person_metadata(req_data, contract_id, now)
            if 'lock' in req_data:
                metadata.lock = req_data['lock']
                metadata.save()
        else:
            if 'value' in req_data and not metadata.lock:
                metadata.value = req_data['value']
            if 'dateValue' in req_data and not metadata.lock:
                metadata.date_value = req_data['dateValue']
            if 'lock' in req_data:
                metadata.lock = req_data['lock']
            metadata.updated_by = self.request.user
            metadata.updated_at = now
            metadata.save()
        return metadata

    def _create_metadata(self, req_data, contract_id, now):
        meta_key = MetaKey.objects.filter(
            Q(account_id=self.request.user.account_id) | Q(account_id__isnull=True),
        ).get(
            id=req_data.get('key_id'),
            status=MetaKey.Status.ENABLE.value,
        )

        metadata = MetaData(
            key=meta_key,
            contract_id=contract_id,
            status=MetaData.Status.ENABLE.value,
        )

        if meta_key.label == 'conpass_person':
            if 'value' in req_data and not metadata.lock:
                self._create_person_metadata(req_data, contract_id, meta_key, now)
            if 'lock' in req_data:
                metadata.lock = req_data['lock']
                metadata.save()

        if 'value' in req_data and not metadata.lock:
            metadata.value = req_data['value']
        if 'dateValue' in req_data and not metadata.lock:
            metadata.date_value = req_data['dateValue']
        if 'lock' in req_data:
            metadata.lock = req_data['lock']
        metadata.created_by = self.request.user
        metadata.created_at = now
        metadata.updated_by = self.request.user
        metadata.updated_at = now
        metadata.save()
        return metadata

    def _update_person_metadata(self, req_data, contract_id, now):

        # カンマ区切りの値を分割してセットに変換
        new_person_ids = set(map(str.strip, req_data['value'].split(',')))

        # 担当者名の既存レコードを取得
        existing_metadata = MetaData.objects.filter(
            contract_id=contract_id,
            key__label='conpass_person',
            status=MetaData.Status.ENABLE.value
        )
        existing_person_ids = set(meta.value for meta in existing_metadata)

        # 削除するID
        ids_to_delete = existing_person_ids - new_person_ids
        MetaData.objects.filter(
            contract_id=contract_id,
            key__label='conpass_person',
            value__in=ids_to_delete
        ).delete()

        # 追加するID
        ids_to_add = new_person_ids - existing_person_ids
        meta_key = MetaKey.objects.filter(label='conpass_person').first()
        if not meta_key:
            raise MetaKey.DoesNotExist("担当者名のMetaKeyが見つかりません。")

        for person_id in ids_to_add:
            MetaData.objects.create(
                key=meta_key,
                contract_id=contract_id,
                value=person_id,
                status=MetaData.Status.ENABLE.value,
                created_by=self.request.user,
                created_at=now,
                updated_by=self.request.user,
                updated_at=now
            )

        # 更新する担当者
        ids_to_update = existing_person_ids & new_person_ids
        for person_id in ids_to_update:
            metadata = MetaData.objects.filter(
                contract_id=contract_id,
                key__label='conpass_person',
                value=person_id
            ).first()
            if metadata:
                metadata.updated_by = self.request.user
                metadata.updated_at = now
                metadata.save()

    def _create_person_metadata(self, req_data, contract_id, meta_key, now):

        # カンマ区切りの値を分割してリストに変換
        new_person_ids = set(map(str.strip, req_data['value'].split(',')))

        for person_id in new_person_ids:
            MetaData.objects.create(
                key=meta_key,
                contract_id=contract_id,
                value=person_id,
                status=MetaData.Status.ENABLE.value,
                created_by=self.request.user,
                created_at=now,
                updated_by=self.request.user,
                updated_at=now,
            )


class ContractMetaDataView(APIView):
    """
    メタデータ単体
    """

    def delete(self, request, metadata_id: int):
        user = self.request.user
        now = make_aware(datetime.datetime.now())

        try:
            metadata = MetaData.objects.filter(pk=metadata_id, status=MetaData.Status.ENABLE.value).get()
        except MetaData.DoesNotExist as e:
            logger.info(e)
            return Response({'msg': ['メタデータが見つかりません']}, status=status.HTTP_400_BAD_REQUEST)

        metadata.status = MetaData.Status.DISABLE.value
        metadata.updated_at = now
        metadata.updated_by = user
        metadata.save()

        return Response()


class ChangeLogListView(APIView):
    """
    １つの契約書に紐づく更新履歴（contract_history）をリストで取得する
    id : 契約書ID
    """
    pass


class CreateContractArchive(APIView):
    """
    条文アーカイブ登録
    """

    def post(self, request):
        req_serializer = ContractArchiveCreateRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            contract = Contract.objects.get(id=req_serializer.data.get('id'))
            # 契約書が無効な場合はエラー（締結済でなくても扱えるようになった）
            if contract.status == Contract.Status.DISABLE:
                return Response({'msg': ['契約書が無効です']}, status=status.HTTP_400_BAD_REQUEST)
            # テンプレートIDがない場合はエラー
            # if not contract.template:
            #     return Response({'msg': ['テンプレートがありません']}, status=status.HTTP_400_BAD_REQUEST)
        except Contract.DoesNotExist as e:
            logger.info(e)
            return Response({'msg': ['契約書が見つかりません']}, status=status.HTTP_400_BAD_REQUEST)

        try:
            c_archive = ContractArchive()
            c_archive.contract_id = req_serializer.data.get("id")
            c_archive.body_text = req_serializer.data.get("dragBody")
            c_archive.reason = req_serializer.data.get("reason")
            c_archive.created_at = make_aware(datetime.datetime.now())
            c_archive.status = ContractArchive.Status.ENABLE.value
            c_archive.created_by_id = self.request.user.id
            c_archive.updated_at = make_aware(datetime.datetime.now())
            c_archive.updated_by_id = self.request.user.id
            c_archive.save()
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response("DBエラーが発生しました", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=status.HTTP_200_OK)


class ContractArchiveList(generics.ListAPIView):
    """
    連絡先一覧画面検索処理
    """
    serializer_class = ContractArchiveListResponseSerializer
    pagination_class = StandardResultsSetPagination

    def get(self, request, *args, **kwargs):
        """
        入力チェックを追加
        """
        req_serializer = ContractArchiveListRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return self.list(request, *args, **kwargs)

    def get_queryset(self):
        """
        検索処理追加のためオーバーライド
        """
        request = self.request
        account_id = self.request.user.account_id
        try:
            Contract.objects.get(pk=request.query_params.get('id'))
        except Contract.DoesNotExist as e:
            logger.error(f'{e}: {traceback.format_exc()}')
            return Response('契約書が存在しません', status=status.HTTP_400_BAD_REQUEST)

        wheres = {
            'contract__account_id': account_id,
            'status': ContractArchive.Status.ENABLE.value,
        }

        # 追加の検索パラメータ
        if request.query_params.get('searchParamsContractName'):
            wheres['contract__name__icontains'] = request.query_params.get('searchParamsContractName')
        if request.query_params.get('searchParamsContractBody'):
            wheres['body_text__icontains'] = request.query_params.get('searchParamsContractBody')
        if request.query_params.get('listSortId'):
            wheres['contract__id'] = request.query_params.get('listSortId')
        # リクエストから 'createdBy' パラメータを取得
        created_by_name = request.query_params.get('searchParamsCreatBy')

        # 'createdBy' パラメータが存在する場合、一致するレコードを検索
        if created_by_name:
            wheres_user = {
                'account_id': account_id,
                'type': User.Type.ACCOUNT.value,
                'is_bpo': False,
                'username__icontains': created_by_name
            }
            # usernameがcreated_by_nameに部分一致するUserオブジェクトを検索
            matching_users = User.objects.filter(**wheres_user)
            created_by_id = [user.id for user in matching_users]
            # 結果のIDリストをクエリに使用
            wheres['created_by_id__in'] = created_by_id

        search_created_date_from = request.query_params.get('searchCreatedDateFrom')
        search_created_date_to = request.query_params.get('searchCreatedDateTo')

        # Convert string dates to datetime objects and set appropriate times
        if search_created_date_from:
            start_date = timezone.datetime.strptime(search_created_date_from, '%Y-%m-%d')
            start_date = timezone.make_aware(datetime.datetime.combine(start_date, datetime.time.min))
            wheres['created_at__gte'] = start_date

        if search_created_date_to:
            end_date = timezone.datetime.strptime(search_created_date_to, '%Y-%m-%d')
            end_date = timezone.make_aware(datetime.datetime.combine(end_date, datetime.time.max))
            wheres['created_at__lte'] = end_date

        # クエリセットを作成
        queryset = ContractArchive.objects.filter(**wheres).order_by('-updated_at', 'id').all()

        return queryset


class ContractArchiveRecent(APIView):
    def get(self, request):
        req_serializer = ContractArchiveRecentRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            contract = Contract.objects.get(pk=req_serializer.data.get('id'))
        except Contract.DoesNotExist as e:
            logger.error(f'{e}: {traceback.format_exc()}')
            return Response('契約書が存在しません', status=status.HTTP_400_BAD_REQUEST)

        recent_archives = ContractArchive.objects.filter(status=ContractArchive.Status.ENABLE.value,
                                                         contract__template_id=contract.template_id,
                                                         contract__id=contract.id
                                                         ).order_by('-created_at', 'id').all()[:RECENT_ARCHIVE_NUM]

        res_serializer = ContractArchiveRecentResponseBodySerializer(recent_archives)
        return Response(data=res_serializer.data)


class DeleteContractArchives(APIView):
    '''
    条文アーカイブを削除
    '''
    def post(self, request):
        req_serializer = ContractArchiveDeleteRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = request.data
        user = self.request.user
        now = make_aware(datetime.datetime.now())
        result_list = []

        for delete_id in list(params['ids']):
            try:
                delete_contract_archive = ContractArchive.objects.get(
                    pk=delete_id,
                    contract__account_id=self.request.user.account_id,
                )
            except ContractArchive.DoesNotExist as e:
                logger.error(f'{e}: {traceback.format_exc()}')
                return Response({'msg': ['アーカイブが見つかりません。']}, status=status.HTTP_400_BAD_REQUEST)

            try:
                delete_contract_archive.status = Statusable.Status.DISABLE.value
                delete_contract_archive.updated_by_id = user.id
                delete_contract_archive.updated_at = now
                delete_contract_archive.save()
            except DatabaseError as e:
                logger.error(f'{e}: {traceback.format_exc()}')
                return Response({'msg': ['DBエラーが発生しました。']}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            result_list.append(delete_id)

        return Response({'results': result_list, 'page_size': settings.REST_FRAMEWORK['PAGE_SIZE']}, status=status.HTTP_200_OK)


class ContractWithMetaListView(ListAPIView):
    serializer_class = ContractBriefInfoSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        # 現在のユーザーが作成したWorkflowに関連するContractのID
        workflow_contract_ids = Workflow.objects.filter(
            created_by=self.request.user
        ).values_list('contract', flat=True)

        # 現在のユーザーが担当者として指定されているMetaDataに関連するContractのID
        conpass_person_contract_ids = MetaData.objects.filter(
            key_id=ContractMetaKeyIdable.MetaKeyId.CONPASS_PERSON.value,
            value=self.request.user.id
        ).values_list('contract', flat=True)

        queryset = Contract.objects.filter(
            Q(created_by=self.request.user) | Q(id__in=workflow_contract_ids) | Q(id__in=conpass_person_contract_ids)
        )

        # 閲覧権限のあるフォルダのみ
        allowed_directories = DirectoryService() \
            .get_allowed_directories(self.request.user, ContractTypeable.ContractType.CONTRACT.value)
        allowed_directory_ids = [directory.id for directory in allowed_directories]
        queryset = (
            queryset.filter(
                account=self.request.user.account,
                directory__id__in=allowed_directory_ids,
                is_garbage=False,
                status__in=[
                    ContractStatusable.Status.SIGNED.value,
                    ContractStatusable.Status.SIGNED_BY_PAPER.value
                ]
            )
            .prefetch_related('meta_data_contract')
        )

        # 契約終了日のサブクエリ
        end_date_subquery = MetaData.objects.filter(
            key_id=ContractMetaKeyIdable.MetaKeyId.CONTRACTENDDATE.value,
            contract=OuterRef('id')
        ).order_by('-date_value').values('date_value')[:1]

        # 解約ノーティス日のサブクエリ用フィルタ
        cancel_notice_filter = MetaData.objects.filter(
            key_id=ContractMetaKeyIdable.MetaKeyId.CANCELNOTICE.value,
            contract=OuterRef('id'),
            date_value__isnull=False
        )
        # 解約ノーティス日のサブクエリ
        cancel_notice_subquery = cancel_notice_filter.order_by('-date_value').values('date_value')[:1]

        # 条件に基づくサブクエリの選択
        queryset = queryset.annotate(
            end_date=Case(
                When(
                    # 解約ノーティス日が存在し、NULLでない場合、その値を使用
                    condition=Exists(cancel_notice_filter),
                    then=Subquery(cancel_notice_subquery, output_field=DateField())
                ),
                # 上記以外の場合、契約終了日を使用
                default=Subquery(end_date_subquery, output_field=DateField())
            )
        )

        queryset = queryset.order_by('end_date')

        # 「契約更新通知」が「通知対象にする」
        queryset = queryset.filter(
            Q(
                meta_data_contract__key_id=ContractMetaKeyIdable.MetaKeyId.CONPASS_CONTRACT_RENEW_NOTIFY.value,
                meta_data_contract__value=1
            )
        )

        # end_date <= (現在+1ヶ月)
        queryset = queryset.filter(end_date__lte=datetime.datetime.now() + relativedelta(months=1))

        # 契約終了日 >= アップロード日
        queryset = queryset.filter(Q(end_date__gte=F('created_at')))

        queryset = queryset.distinct()

        return queryset


class UpdateContractRenewNotify(generics.GenericAPIView):
    serializer_class = UpdateContractRenewNotifySerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            error_msg = serializer.errors.get('contract_ids', ["Unknown error"])[0]
            return Response({'msg': error_msg}, status=status.HTTP_400_BAD_REQUEST)

        contract_ids = serializer.validated_data['contract_ids']
        MetaData.objects.filter(
            contract_id__in=contract_ids,
            key_id=ContractMetaKeyIdable.MetaKeyId.CONPASS_CONTRACT_RENEW_NOTIFY.value
        ).update(value=0)

        return Response(status=status.HTTP_200_OK)


class ContractZipDownload(APIView, GoogleCloudStorage):
    def post(self, request):

        req_serializer = ContractZipDownloadRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_id = self.request.user.id
        contract_ids = req_serializer.data.get('idList')
        zip_name = 'conpass-contracts-{0}'.format(datetime.datetime.now().replace(tzinfo=None).strftime('%Y%m%d%H%M%S'))

        # 一時ディレクトリ作成・PDF作成・zip作成
        try:
            self.set_user_id(user_id)
            with tempfile.TemporaryDirectory() as temp_dir, zipfile.ZipFile(zip_name, 'w') as zp:
                for c_id in contract_ids:
                    contract = Contract.objects.get(pk=c_id)
                    # 契約書ステータスによってダウンロードファイルを変更
                    # 締結済はストレージから取得
                    c_file = contract.file.exclude(type=File.Type.ETC.value).order_by('-created_at', 'id').first()
                    if not c_file:  # 紐づいているファイルが無い契約書はスキップ
                        continue
                    file_id = c_file.id

                    file = self.get_file_from_id(file_id)
                    file_name, file_url = file.name, file.url
                    if not file_name or not file_url:
                        raise Exception('ファイルが見つかりません')

                    client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
                    blob = bucket.blob(file_url)  # GCS側
                    download_path = os.path.join(temp_dir, file.name)
                    blob.download_to_filename(download_path)
                    zp.write(download_path, arcname='{0}-{1}'.format(contract.id, file.name))

            # zipファイルをbase64エンコード
            with open(os.path.join(zip_name), 'rb') as zp:
                b64 = base64.b64encode(zp.read())

            # Base64エンコード後のサイズ + ファイル名の長さを確認
            encoded_size = len(b64)
            name_size = len(zip_name.encode())  # UTF-8でエンコードされたファイル名のバイト数
            total_size = encoded_size + name_size

            # 32MBを少し余裕を持ってチェックするため31MBでチェック
            if total_size > 31 * 1024 * 1024:
                return Response({'msg': ['ファイルサイズが大きいためダウンロードできません']}, status=status.HTTP_400_BAD_REQUEST)

        except Contract.DoesNotExist as e:
            logger.info(e)
            return Response({'msg': ['契約書が見つかりません']}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'{e}: {traceback.format_exc()}')
            return Response({'msg': ['エラーが発生しました']}, status=status.HTTP_400_BAD_REQUEST)
        finally:
            self.set_user_id(0)
            # zipファイル削除
            if os.path.exists(os.path.join(zip_name)):
                os.remove(os.path.join(zip_name))

        response = {
            'name': zip_name,
            'base64data': b64,
        }
        # TODO 確認用のためあとで try except を消す
        try:
            return Response(response, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f'{e}: {traceback.format_exc()}')
            return Response({'msg': [str(e)]}, status=status.HTTP_400_BAD_REQUEST)


class ContractSearchSettingList(APIView):
    """
    契約書検索設定用
    """

    def get(self, request):
        """
        契約書検索項目取得
        """
        req_serializer = ContractSearchSettingRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        """
        cookie取得
        cookieは下記の形式
        default,free,status,createdAtのカテゴリーごとに&区切り
        カテゴリー内は{カテゴリー名}:{'|'区切りで表示するメタ情報のid}
        固定項目はそのまま0,1が入る
        例) default:1|2&free:&status:True&createdAt:False
        →仕様の変更により、cookieからLocal Storageに変更(2025.01)
        """
        contract_type = req_serializer.data.get('type')
        if contract_type == 1:
            cookie_name = COOKIE_NAME
        elif contract_type == 2:
            cookie_name = COOKIE_NAME_TEMPLATE
        else:
            cookie_name = COOKIE_NAME_BULK
        setting_cookie = request.COOKIES.get(cookie_name, '')
        page_size = settings.REST_FRAMEWORK['PAGE_SIZE']
        setting_list = setting_cookie.split('&')
        for sc in setting_list:
            s_item = sc.split(':')
            if s_item[0] == 'pageSize':
                page_size = int(s_item[1])

        results = {
            'status': {'checked': False, 'value': ''},
            'created_at': {'checked': False},
            'is_open': {'checked': False},
            'company': {'checked': False},
            'file_name': {'checked': False},
        }

        # メタ情報-デフォルト項目
        default_list = MetaKey.objects.filter(status=MetaKey.Status.ENABLE.value,
                                              type=MetaKey.Type.DEFAULT.value).all()
        for default in default_list:
            default.checked = False
            # 日付項目はfrom~toで表示する
            if default.id in META_INFO_DATE:
                default.isDate = True
            else:
                default.isDate = False
        results['default_list'] = list(default_list)

        # メタ情報-自由項目
        free_list = MetaKey.objects.filter(status=MetaKey.Status.ENABLE.value,
                                           type=MetaKey.Type.FREE.value,
                                           account_id=self.request.user.account_id).all()
        for free in free_list:
            free.checked = False
            free.isDate = False
        results['free_list'] = list(free_list)

        # page_size取得
        results['page_size'] = page_size

        res_serializer = ContractSearchSettingResponseBodySerializer(results)
        return Response(data=res_serializer.data)

    def post(self, request):
        """
        契約書検索設定保存
        """
        req_serializer = ContractSearchSettingEditRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        contract_type = req_serializer.data.get('type')
        if contract_type == 1:
            cookie_name = COOKIE_NAME
        elif contract_type == 2:
            cookie_name = COOKIE_NAME_TEMPLATE
        else:
            cookie_name = COOKIE_NAME_BULK
        default_str = '|'.join(map(str, req_serializer.data.get('defaultList')))
        free_str = '|'.join(map(str, req_serializer.data.get('freeList')))
        # cookieの例) default:1|2&free:&status:True&createdAt:False
        cookie_val = 'default:{0}&free:{1}&status:{2}&createdAt:{3}&isOpen:{4}&company:{5}' \
            .format(default_str,
                    free_str,
                    req_serializer.data.get('checkedStatus'),
                    req_serializer.data.get('checkedCreatedAt'),
                    req_serializer.data.get('checkedIsOpen'),
                    req_serializer.data.get('checkedCompany'))

        res = Response(status=status.HTTP_200_OK)
        res.set_cookie(cookie_name, cookie_val, max_age=60 * 60 * 24 * 7)

        return res


class ContractPageSize(APIView):
    def post(self, request):
        """
        契約書一覧のページサイズ保存
        """
        # 既存のCookieから値を取得
        existing_cookie_val = request.COOKIES.get(COOKIE_NAME, '')
        # 既存のpage_sizeを取得、またはデフォルト値を設定
        default_page_size = settings.REST_FRAMEWORK['PAGE_SIZE']
        page_size = request.data.get('page_size', default_page_size)
        new_page_size = int(page_size['value'])

        # 新しいpage_sizeを既存のCookieに追加するための文字列を作成
        if 'pageSize' in existing_cookie_val:
            # 既にpage_sizeが設定されている場合は、新しい値で更新
            parts = existing_cookie_val.split('&')
            new_cookie_parts = []
            for part in parts:
                if 'pageSize:' in part:
                    # 新しいpageSizeの値に置換
                    new_cookie_parts.append('pageSize:{}'.format(new_page_size))
                else:
                    new_cookie_parts.append(part)
            new_cookie_val = '&'.join(new_cookie_parts)
        else:
            # まだpage_sizeが設定されていない場合は、追加
            new_cookie_val = existing_cookie_val + ('&' if existing_cookie_val else '') + 'pageSize:{}'.format(
                new_page_size)

        # 新しいCookie値をセット
        res = Response(status=status.HTTP_200_OK)
        res.set_cookie(COOKIE_NAME, new_cookie_val, max_age=60 * 60 * 24 * 7)

        return res


class ContractDataList(APIView):
    """
    契約書の素のデータ一覧取得
    """

    def get(self, request):
        """
        契約書検索項目取得
        """
        req_serializer = ContractDataListRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        contract_service = ContractService()
        contract_list = contract_service.get_contract_all_list(req_serializer.data, self.request.user)

        res_serializer = ContractDataListResponseBodySerializer(contract_list)
        return Response(data=res_serializer.data)


class ContractDirectoryList(APIView):
    """
    移動先のディレクトリ一覧取得
    """

    def get(self, request):
        req_serializer = ContractDirectoryListRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        wheres = {
            'account_id': self.request.user.account_id,
            'status': Directory.Status.ENABLE.value,
            'level': 0
        }
        if req_serializer.data.get('type'):
            wheres['type'] = req_serializer.data.get('type')
        directory_service = DirectoryService()
        prefetch = directory_service.get_permission_prefetch(self.request.user)
        directories = list(Directory.objects.filter(**wheres).all().annotate(
            sort_id_is_null=Case(
                When(sort_id__isnull=True, then=Value(True)),
                default=Value(False),
                output_field=BooleanField()
            )
        ).order_by('sort_id_is_null', 'sort_id', 'name')
            .prefetch_related(prefetch))
        results = []
        for d in list(directories):
            results.append(d)
            results.extend(Directory.objects.filter(
                account_id=self.request.user.account_id,
                status=Directory.Status.ENABLE.value,
                level=1,
                parent_id=d.id,
            ).all().annotate(
                sort_id_is_null=Case(
                    When(sort_id__isnull=True, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField()
                )
            ).order_by('sort_id_is_null', 'sort_id', 'name').prefetch_related(prefetch))

        visible_results = directory_service.filter_visible_directories(results, self.request.user.is_bpo)

        res_serializer = ContractDirectoryListResponseBodySerializer(visible_results)

        return Response(data=res_serializer.data)


class ContractDirectoryUpdate(APIView):
    """
    ディレクトリ移動
    """

    def post(self, request):
        req_serializer = ContractDirectoryUpdateRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            target_list = Contract.objects.filter(id__in=req_serializer.data.get('idList'),
                                                  account_id=self.request.user.account_id)
            # すでにステータスが「無効」になっているレコードが選択された場合は変更不可
            status_list = [con.status for con in target_list]
            if status_list.count(Contract.Status.DISABLE.value) > 0:
                return Response({'msg': '削除済みの契約書は変更できません'}, status=status.HTTP_400_BAD_REQUEST)

            target_list.update(directory_id=req_serializer.data.get('directoryId'),
                               is_garbage=False,
                               updated_at=make_aware(datetime.datetime.now()),
                               updated_by_id=self.request.user.id,
                               )

            notify_to_AI_agent.delay(req_serializer.data.get('idList'), AIAgentNotifyEnum.UPDATED.value)

        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({'msg': 'DBエラーが発生しました'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_200_OK)


class ContractCancel(APIView):
    """
    契約書の解約
    """

    def post(self, request):
        req_serializer = ContractStatusUpdateRequestBodySerializer(data=request.data)

        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            contract = Contract.objects.get(id=req_serializer.data.get('id'))
            contract.status = Contract.Status.CANCELED.value
            contract.updated_at = make_aware(datetime.datetime.now())
            contract.updated_by = self.request.user
            contract.save()

        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({'msg': 'DBエラーが発生しました'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_200_OK)


class ContractExpire(APIView):
    """
    契約書の満了
    """

    def post(self, request):
        req_serializer = ContractStatusUpdateRequestBodySerializer(data=request.data)

        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            contract = Contract.objects.get(id=req_serializer.data.get('id'))
            contract.status = Contract.Status.EXPIRED.value
            contract.updated_at = make_aware(datetime.datetime.now())
            contract.updated_by = self.request.user
            contract.save()

        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({'msg': 'DBエラーが発生しました'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_200_OK)


class ContractReturn(APIView):
    """
    契約書の解約および解約からの復帰
    """

    def post(self, request):
        req_serializer = ContractStatusUpdateRequestBodySerializer(data=request.data)

        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        using_adobe_sign = AdobeSign.objects.filter(contract_id=req_serializer.data.get('id'),
                                                    status=AdobeSign.Status.ENABLE.value).exists()

        if using_adobe_sign:
            newStatus = Contract.Status.SIGNED.value
        else:
            newStatus = Contract.Status.SIGNED_BY_PAPER.value

        try:
            contract = Contract.objects.get(id=req_serializer.data.get('id'))
            contract.status = newStatus
            contract.updated_at = make_aware(datetime.datetime.now())
            contract.updated_by = self.request.user
            contract.save()

        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({'msg': 'DBエラーが発生しました'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_200_OK)


class ContractGarbageUpdate(APIView):
    """
    契約書をゴミ箱に移動
    """

    def post(self, request):
        req_serializer = ContractGarbageUpdateRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            Contract.objects.filter(id__in=req_serializer.data.get('idList'),
                                    account_id=self.request.user.account_id) \
                .update(is_garbage=True,
                        updated_at=make_aware(datetime.datetime.now()),
                        updated_by_id=self.request.user.id,
                        )

        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({'msg': 'DBエラーが発生しました'}, status=status.HTTP_400_BAD_REQUEST)
        notify_to_AI_agent.delay(req_serializer.data.get('idList'), AIAgentNotifyEnum.DELETED.value)
        return Response(status=status.HTTP_200_OK)


class ContractOpen(APIView):
    """
    契約書を公開
    """

    def post(self, request):
        req_serializer = ContractOpenRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            Contract.objects.filter(id__in=req_serializer.data.get('idList'),
                                    account_id=self.request.user.account_id) \
                .update(is_open=True,
                        updated_at=make_aware(datetime.datetime.now()),
                        updated_by_id=self.request.user.id,
                        )

        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({'msg': 'DBエラーが発生しました'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_200_OK)


class ContractGarbageDelete(APIView):
    """
    ゴミ箱の契約書を削除状態に変更
    """

    def post(self, request):
        req_serializer = ContractGarbageUpdateRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            Contract.objects.filter(id__in=req_serializer.data.get('idList'),
                                    account_id=self.request.user.account_id) \
                .update(status=Contract.Status.DISABLE.value,
                        updated_at=make_aware(datetime.datetime.now()),
                        updated_by_id=self.request.user.id,
                        )

        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({'msg': 'DBエラーが発生しました'}, status=status.HTTP_400_BAD_REQUEST)
        notify_to_AI_agent.delay(req_serializer.data.get('idList'), AIAgentNotifyEnum.DELETED.value)
        return Response(status=status.HTTP_200_OK)


class ContractBodyList(APIView):
    """
    契約書本文の一覧を取得
    更新された本文
    更新日時
    更新者
    """

    def get(self, request):
        """
        契約書検索項目取得
        """
        req_serializer = ContractDataListRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        contract_service = ContractService()
        contract_list = contract_service.get_contract_all_list(req_serializer.data, self.request.user)

        res_serializer = ContractDataListResponseBodySerializer(contract_list)
        return Response(data=res_serializer.data)


class RelatedContractsView(generics.ListAPIView):
    serializer_class = ContractBriefInfoSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        # 権限があるフォルダのみ
        allowed_directories = DirectoryService().get_allowed_directories(self.request.user,
                                                                         ContractTypeable.ContractType.CONTRACT.value)
        allowed_directory_ids = [directory.id for directory in allowed_directories]

        contract = get_object_or_404(Contract, id=self.kwargs['contract_id'])
        return contract.related_contracts \
            .filter(directory__id__in=allowed_directory_ids, is_garbage=False) \
            .prefetch_related('meta_data_contract')

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        contract = get_object_or_404(Contract, id=self.kwargs['contract_id'])
        related_contract_id = request.data.get('related_contract_id')
        action = request.data.get('action')

        if not related_contract_id or not action:
            return Response({"error": "リクエストが間違っている"}, status=status.HTTP_400_BAD_REQUEST)

        related_contract = get_object_or_404(Contract, id=related_contract_id)

        if action == "add":
            contract.related_contracts.add(related_contract)
            related_contract.related_contracts.add(contract)
        elif action == "remove":
            contract.related_contracts.remove(related_contract)
            related_contract.related_contracts.remove(contract)
        else:
            return Response({"error": "無効なアクション"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(related_contract).data)


class AccountContractsView(generics.ListAPIView):
    serializer_class = ContractBriefInfoSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        # 権限があるフォルダのみ
        allowed_directories = DirectoryService().get_allowed_directories(self.request.user,
                                                                         ContractTypeable.ContractType.CONTRACT.value)
        allowed_directory_ids = [directory.id for directory in allowed_directories]

        contract = get_object_or_404(Contract, id=self.kwargs['contract_id'])
        # 開かれたページの契約書と関連契約書はのぞいて、観覧権限のあるフォルダの契約書を取得
        related_contract_ids = list(contract.related_contracts.values_list('id', flat=True))
        queryset = Contract.objects \
            .filter(account=self.request.user.account, directory__id__in=allowed_directory_ids, is_garbage=False) \
            .exclude(id__in=related_contract_ids + [contract.id]) \
            .prefetch_related('meta_data_contract')
        # リクエストパラメーターから検索ワードを取得する
        search_term = self.request.query_params.get('search_term', None)
        if search_term and search_term.strip():
            search_words = search_term.split()
            # 各検索ワードに対して、nameかmeta_data_contract__valueのどちらかに含まれているQオブジェクトを生成する
            conditions = [Q(name__icontains=word) | Q(meta_data_contract__value__icontains=word) for word in
                          search_words]
            # 検索ワードのどれかが含まれているものだけをフィルターする
            queryset = queryset.filter(reduce(or_, conditions))
        queryset = queryset.distinct()
        return queryset


class ContractMetaKeyFreeList(APIView):
    """
    契約書のMetaKeyのFree項目を取得
    """

    def get(self, request):
        # メタ情報-自由項目
        free_list = MetaKey.objects.filter(status=MetaKey.Status.ENABLE.value,
                                           type=MetaKey.Type.FREE.value,
                                           account_id=self.request.user.account_id).order_by('id').all()

        res_serializer = ContractMetaKeyListResponseBodySerializer(free_list, many=True)
        return Response(data=res_serializer.data)


class ContractMetadataCsvDownload(APIView):
    DATE_HEADERS = ["契約日", "契約開始日", "契約終了日", "関連契約日"]

    def get(self, request):
        start_time = time.perf_counter()

        req_serializer = ContractListRequestBodySerializer(data=self.request.query_params)
        req_serializer.is_valid(raise_exception=True)

        service = ContractService()
        contracts = service.query_search(user=self.request.user, params=req_serializer.data)
        if not contracts.exists():
            return Response({"message": "対象はありません"}, status=200)

        step1_time = time.perf_counter()
        logger.info(f"契約検索完了: {step1_time - start_time:.4f}秒")

        base_dir = os.path.dirname(__file__)
        sample_file_path = os.path.join(base_dir, "meta_data_sample", "meta_data_sample.csv")

        if not os.path.exists(sample_file_path):
            return Response({"error": f"サンプルCSVファイルが見つかりません: {sample_file_path}"}, status=404)

        with open(sample_file_path, newline='', encoding='utf-8') as sample_file:
            sample_reader = csv.reader(sample_file)
            sample_rows = list(sample_reader)

        base_header = sample_rows[0]

        step2_time = time.perf_counter()
        logger.info(f"サンプルCSV読み込み完了: {step2_time - step1_time:.4f}秒")

        free_meta_keys = list(MetaKey.objects.filter(
            status=MetaKey.Status.ENABLE.value,
            type=MetaKey.Type.FREE.value,
            account_id=self.request.user.account.id,
        ).order_by('id').values_list('name', flat=True))

        updated_header = base_header + free_meta_keys

        step3_time = time.perf_counter()
        logger.info(f"自由項目MetaKey取得完了: {step3_time - step2_time:.4f}秒")

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="contracts_metadata.csv"'
        response.write('\ufeff'.encode('utf-8'))

        writer = csv.writer(response)
        writer.writerow(updated_header)

        for row in sample_rows[1:4]:
            writer.writerow(row)

        # 事前に関連データを取得
        contract_ids = contracts.values_list("id", flat=True)

        step4_time = time.perf_counter()
        logger.info(f"契約ID取得完了: {step4_time - step3_time:.4f}秒")

        metadata_qs = MetaData.objects.filter(
            contract_id__in=contract_ids,
            status=Statusable.Status.ENABLE.value
        ).select_related('key').order_by('key__name', 'id')

        contract_metadata_dict = {}
        for meta in metadata_qs:
            if meta.contract_id not in contract_metadata_dict:
                contract_metadata_dict[meta.contract_id] = {}
            if meta.key.name not in contract_metadata_dict[meta.contract_id]:
                contract_metadata_dict[meta.contract_id][meta.key.name] = {
                    "value": meta.value,
                    "date_value": meta.date_value
                }

        step5_time = time.perf_counter()
        logger.info(f"メタデータ取得完了: {step5_time - step4_time:.4f}秒")

        assigned_users_qs = MetaData.objects.filter(
            contract_id__in=contract_ids, key__name="担当者名"
        ).values_list("contract_id", "value")

        user_ids = {int(value) for _, value in assigned_users_qs if value.isdigit()}
        users = {user.id: user.username for user in User.objects.filter(
            id__in=user_ids,
            status=User.Status.ENABLE.value,
            account_id=self.request.user.account.id
        )}

        contract_assigned_users = {}
        for contract_id, value in assigned_users_qs:
            if value.isdigit():
                user_name = users.get(int(value))
                if user_name:
                    contract_assigned_users.setdefault(contract_id, []).append(user_name)

        step6_time = time.perf_counter()
        logger.info(f"担当者情報取得完了: {step6_time - step5_time:.4f}秒")

        cancel_notice_qs = MetaData.objects.filter(
            contract_id__in=contract_ids, key__name="解約ノーティス日"
        ).values_list("contract_id", "value", "date_value")

        contract_cancel_notices = {
            contract_id: (value, date_value)
            for contract_id, value, date_value in cancel_notice_qs
        }

        step7_time = time.perf_counter()
        logger.info(f"解約ノーティス日取得完了: {step7_time - step6_time:.4f}秒")

        file_data = (
            File.objects
            .filter(contract_files__in=contract_ids)
            .exclude(type=File.Type.ETC.value)
            .order_by("created_at")
            .values("contract_files__id", "name")
        )

        # Use dict comprehension with seen set
        contract_files = {}
        seen = set()

        for file in file_data:
            contract_id = file["contract_files__id"]
            if contract_id not in seen:
                contract_files[contract_id] = file["name"]
                seen.add(contract_id)

        step8_time = time.perf_counter()
        logger.info(f"ファイル情報取得完了: {step8_time - step7_time:.4f}秒")

        for contract in contracts:
            contract_id = contract.id
            assigned_users_str = '|'.join(contract_assigned_users.get(contract_id, []))
            file_name = contract_files.get(contract_id, '')
            dir_path = service.generate_contract_directory_path(contract)

            cancel_notice_value, cancel_notice_date_value = contract_cancel_notices.get(contract_id, ("", ""))

            row = [
                contract_id,
                dir_path,
                file_name,
            ]

            for meta_key_name in updated_header[3:]:
                if meta_key_name == "担当者ユーザー":
                    row.append(assigned_users_str)
                elif meta_key_name == "担当者グループ":
                    row.append("")
                elif meta_key_name == "解約ノーティス日":
                    row.append(cancel_notice_value)
                elif meta_key_name == "解約ノーティス日(日付)":
                    row.append(cancel_notice_date_value)
                elif meta_key_name in self.DATE_HEADERS:
                    row.append(contract_metadata_dict.get(contract_id, {}).get(meta_key_name, {}).get("date_value", ""))
                else:
                    row.append(contract_metadata_dict.get(contract_id, {}).get(meta_key_name, {}).get("value", ""))

            writer.writerow(row)

        step9_time = time.perf_counter()
        logger.info(f"CSVデータ作成完了: {step9_time - step8_time:.4f}秒")

        return response


class ContractBlankMetadataCsvDownload(APIView):

    def get(self, request):
        # 現在のファイルのディレクトリからmeta_data_sample.csvへの絶対パスを作成
        base_dir = os.path.dirname(__file__)  # 現在のviews.pyファイルのディレクトリ
        sample_file_path = os.path.join(base_dir, "meta_data_sample", "meta_data_sample.csv")

        # ファイルが存在しない場合のエラー処理
        if not os.path.exists(sample_file_path):
            return Response({"error": f"サンプルCSVファイルが見つかりません: {sample_file_path}"}, status=404)

        # サンプルCSVを読み込む
        with open(sample_file_path, newline='', encoding='utf-8') as sample_file:
            sample_reader = csv.reader(sample_file)
            sample_rows = list(sample_reader)

        # サンプルのヘッダー（1行目）を取得
        base_header = sample_rows[0]  # 1行目のヘッダー

        # PDF名列のインデックスを特定（存在する場合のみ）
        try:
            pdf_name_index = base_header.index("PDF名")
        except ValueError:
            pdf_name_index = None  # PDF名列が存在しない場合はNone

        # 自由項目のヘッダーを取得して統合
        free_meta_keys = MetaKey.objects.filter(
            status=MetaKey.Status.ENABLE.value,
            type=MetaKey.Type.FREE.value,
            account_id=self.request.user.account.id,
        ).order_by('id')
        free_meta_key_names = [meta_key.name for meta_key in free_meta_keys]
        updated_header = base_header + free_meta_key_names  # 自由項目ヘッダーを追加

        # PDF名列を削除
        if pdf_name_index is not None:
            del updated_header[pdf_name_index]

        # HTTPレスポンスをCSV形式にする
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="contracts_blank_metadata.csv"'

        # UTF-8 BOMを追加
        response.write('\ufeff'.encode('utf-8'))  # BOMの追加

        # CSVライターの初期化
        writer = csv.writer(response)

        # ヘッダー行を書き込み
        writer.writerow(updated_header)

        # サンプルデータからPDF名列を削除して書き込み
        for row in sample_rows[1:4]:
            if pdf_name_index is not None:
                del row[pdf_name_index]
            writer.writerow(row)

        return response


class ContractMetadataCsvUpload(APIView):
    """
    契約メタデータのCSVアップロード
    """
    parser_classes = [FormParser, MultiPartParser]

    def post(self, request):
        """
        POSTリクエストでCSVを受け取り、メタデータを登録・更新する
        """
        try:
            # CSVデータの取得
            csv_file = request.FILES.get('csv')
            if not csv_file:
                return Response({
                    'success': False,
                    'msg': 'CSVファイルが提供されていません'
                }, status=status.HTTP_400_BAD_REQUEST)

            # CSV内容のデコード
            csv_contents = csv_file.read().decode('utf-8')

            # BOMがある場合は取り除く
            if csv_contents.startswith('\ufeff'):
                csv_contents = csv_contents.lstrip('\ufeff')

            # インポーターの初期化とバリデーション
            importer = MetaDataCsvImporter(contents=csv_contents, operated_by=request.user)
            if not importer.is_valid():
                return Response({
                    'success': False,
                    'msg': 'CSVデータが無効です',
                    'errors': importer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)

            # メタデータのインポート
            importer.import_metadata()

        except Exception as ex:
            # エラーの詳細をレスポンスに含める
            error_message = str(ex)
            stack_trace = traceback.format_exc()
            return Response({
                'success': False,
                'msg': 'エラーが発生しました',
                'error_message': error_message,
                'stack_trace': stack_trace,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 成功レスポンス
        return Response({'success': True, 'msg': 'メタデータが正常にアップロードされました'})
