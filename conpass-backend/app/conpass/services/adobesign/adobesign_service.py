import datetime
import io
import json
import os
import urllib.parse
from logging import getLogger
from typing import Optional
import traceback
import requests
from django.conf import settings
from django.utils.timezone import make_aware
from requests import Response
from rest_framework import status

from conpass.models import AdobeSetting, User, Workflow, ContractBody, File, Contract, AdobeSign
from conpass.services.contract.contract_service import ContractService
from conpass.services.gcp.cloud_storage import GoogleCloudStorage, GCSBucketName

logger = getLogger(__name__)

ADOBESIGN_API_REFRESH_TOKEN_PATH = 'oauth/v2/refresh'
ADOBESIGN_API_BASE_URIS_PATH = 'api/rest/v6/baseUris'
ADOBESIGN_API_TRANSIENT_DOCUMENTS_PATH = 'api/rest/v6/transientDocuments'
ADOBESIGN_API_COMBINED_DOCUMENT_PATH = 'api/rest/v6/agreements/{}/combinedDocument'
ADOBESIGN_API_GET_SIGNING_URL = 'api/rest/v6/agreements/{}/signingUrls'


class AdobeSignService:

    def _api_request(self, api_path: str, is_post: bool, params: dict, files: Optional[dict],
                     adobe_setting: AdobeSetting, user: User) -> Response:
        """
        APIリクエストをします
        """
        self.refresh_access_token(adobe_setting, user)

        access_token = adobe_setting.access_token
        base_uri = settings.ADOBESIGN_API_ACCESS_POINT

        endpoint = base_uri + api_path

        # headerでコンテンツタイプを指定
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': 'Bearer ' + access_token,
        }
        if is_post:
            if files:
                del headers['Content-Type']
                r = requests.post(url=endpoint, data=params, headers=headers, files=files)
            else:
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
                post_params = urllib.parse.urlencode(params)
                r = requests.post(url=endpoint, data=post_params, headers=headers)
        else:
            r = requests.get(url=endpoint, params=params, headers=headers)
        return r

    def refresh_access_token(self, adobe_setting: AdobeSetting, user: User):
        """
        access_token をリフレッシュする
        access_token は expire が3600（=おそらく１時間）しか無いので基本的に毎回呼んで更新する
        """
        refresh_token = adobe_setting.refresh_token

        baseUri = settings.ADOBESIGN_API_ACCESS_POINT
        endpoint = baseUri + ADOBESIGN_API_REFRESH_TOKEN_PATH

        data = {
            'grant_type': 'refresh_token',
            'client_id': adobe_setting.application_id,
            'client_secret': adobe_setting.client_secret,
            'refresh_token': refresh_token,
        }

        # URLをエンコード
        params = urllib.parse.urlencode(data)
        # headerでコンテンツタイプを指定
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        r = requests.post(url=endpoint, data=params, headers=headers)

        if r.status_code == status.HTTP_200_OK:
            context = json.loads(r.text)
            adobe_setting.access_token = context['access_token']
            adobe_setting.expires_in = context['expires_in']
            adobe_setting.updated_at = make_aware(datetime.datetime.now())
            adobe_setting.updated_by = user
            adobe_setting.save()
        return r

    def get_base_uris(self, adobe_setting: AdobeSetting, user: User):
        """
        baseUrisを取得する
        base UriはAPI用とWEB用がある
        API用：通常のAPIのもの
        WEB用：サブドメインがsecureのもの。OAuthなどで使われます
        ※リブランドなどでドメイン名が変わる可能性がある
        基本的に確認用です
        """
        r = self._api_request(ADOBESIGN_API_BASE_URIS_PATH, False, {}, None, adobe_setting, user)
        # 以下を確認できる
        # context = json.loads(r.text)
        # context['apiAccessPoint']
        # context['webAccessPoint']
        return r

    def transient_documents(self, workflow: Workflow, adobe_setting: AdobeSetting, user: User):
        # AdobeSignの transientDocument を作成
        # workflowの契約書の本文をもとにpdfを作成、それを利用します

        # 最新のbodyを使う
        c_body = ContractBody.objects.filter(status=ContractBody.Status.ENABLE.value,
                                             contract_id=workflow.contract.id).order_by('-created_at', 'id').first()
        if not c_body:
            raise ContractBody.DoesNotExist()

        # url decode しておく
        decoded_body = urllib.parse.unquote(c_body.body)

        # PDF作成
        contract_service = ContractService()
        pdf = contract_service.create_pdf(workflow.contract.name, decoded_body)
        with open(pdf, 'rb') as fsrc:
            str_buffer = fsrc.read()
        os.remove(pdf)

        filename = workflow.contract.name

        # アクセストークン更新
        data = {
            'Mime-Type': 'application/pdf',
            'FIle-Name': filename,
        }
        files = {
            'File': str_buffer,
        }
        # 契約書のアップロード
        r = self._api_request(ADOBESIGN_API_TRANSIENT_DOCUMENTS_PATH, True, data, files, adobe_setting, user)
        return r

    def combined_document(self, agreement: dict, adobe_setting: AdobeSetting, user: User):
        """
        署名済pdfファイルをAdobeSignからダウンロードする
        バイナリデータは r.content の方を見る
        """
        path = ADOBESIGN_API_COMBINED_DOCUMENT_PATH
        path = path.format(agreement['id'])
        r = self._api_request(path, False, {}, None, adobe_setting, user)
        return r

    def get_signing_url(self, agreement_id: str, adobe_setting: AdobeSetting, user: User):
        """
        電子署名用のURLをAdobeSignから取得する
        """
        path = ADOBESIGN_API_GET_SIGNING_URL
        path = path.format(agreement_id)
        r = self._api_request(path, False, {}, None, adobe_setting, user)
        return r
