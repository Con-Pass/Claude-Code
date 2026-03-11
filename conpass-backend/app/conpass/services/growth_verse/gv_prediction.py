import json
import datetime
import io
import requests
import pikepdf
import unicodedata
import dataclasses
import dataclasses_json
from .gv_utils import GvUtils
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google.cloud.storage import Blob

from ..contract.contract_service import ContractService
from ..gcp.vision import GoogleCloudVision
from ..gcp.vision_service import VisionService
from ..gcp.dto.pdf_info import PdfInfo
from ..gcp.cloud_storage import GoogleCloudStorage
from ..azure.azure_prediction import AzurePredict
from ...models import LeaseKey

from common.utils.http_utils import generate_random_string, dumpRequest, dumpResponse
from django.conf import settings
from logging import getLogger

from .serializer.gv_prediction_serializer import PredictionListSerializer

logger = getLogger(__name__)


class PredictionResult:
    entity: str
    filename: str
    score: float
    content: str
    start: int
    end: int


class Predictions:
    predictions: [PredictionResult]
    body: str
    pdf_page_size: int


class GvPredictionResultFormat:
    # １つ目のリストはファイル単位
    files: [Predictions]


@dataclasses_json.dataclass_json
@dataclasses.dataclass
class GvPredictionRequestFile:
    id: int
    url: str


class GvPredict():
    # フロントエンドと2重管理になってしまうため局所的に定義をしておく
    # ※項目を追加する場合は、"resources/constants/config.ts" 内の
    # 　"ConpassContractType" にも追加をすること
    ConpassContractType = [
        {'type': 1, 'name': "秘密保持契約書"},
        {'type': 2, 'name': "雇用契約書"},
        {'type': 3, 'name': "申込注文書"},
        {'type': 4, 'name': "業務委託契約書"},
        {'type': 5, 'name': "売買契約書"},
        {'type': 6, 'name': "請負契約書"},
        {'type': 7, 'name': "賃貸借契約書"},
        {'type': 8, 'name': "派遣契約書"},
        {'type': 9, 'name': "金銭消費貸借契約"},
        {'type': 10, 'name': "代理店契約書"},
        {'type': 11, 'name': "業務提携契約書"},
        {'type': 12, 'name': "ライセンス契約書"},
        {'type': 13, 'name': "顧問契約書"},
        {'type': 14, 'name': "譲渡契約書"},
        {'type': 15, 'name': "和解契約書"},
        {'type': 16, 'name': "誓約書"},
        {'type': 17, 'name': "その他"},
    ]

    def __init__(self):
        self.gv_entity_extraction_gpt_endpoint = settings.GV_ENTITY_EXTRACTION_GPT_ENDPOINT
        self.gv_ocr_gemini_endpoint = settings.GV_OCR_GEMINI_ENDPOINT
        self.gv_lease_identification_gpt_endpoint= settings.GV_LEASE_IDENTIFICATION_GPT_ENDPOINT
        self.vision_service = VisionService()
        self.google_cloud_vision = GoogleCloudVision()

    def _get_conpass_contract_type_by_name(self, name: str):
        for item in self.ConpassContractType:
            if item['name'] == name:
                return item['type']
        # デフォルトは18とする
        # see: https://lbsk.backlog.com/view/PURPLE_PJ-714#comment-449483996
        return 18
    @staticmethod
    def get_meta_value(meta_data, meta_key):
        for data in meta_data:
            if data['entity'] == meta_key:
                return data['content']
        return None

    def _get_pdf_info(self, pdf_blob: Blob) -> PdfInfo:
        pdf_binary = pdf_blob.download_as_string()
        bytes_io = io.BytesIO(pdf_binary)
        with pikepdf.open(bytes_io) as pdf:
            page_size = len(pdf.pages)
        pdf_info = PdfInfo(
            bucket_name=pdf_blob.bucket.name,
            blob_name=pdf_blob.name,
            blob_size=pdf_blob.size,
            page_size=page_size,
            contents=pdf_binary,
        )
        logger.info('GCS PDF情報', extra={
            'info': {
                'bucket_name': pdf_info.bucket_name,
                'blob_name': pdf_info.blob_name,
                'blob_size': pdf_info.blob_size,
                'page_size': pdf_info.page_size,
            }
        })
        return pdf_info

    def _to_predicts(self, pdf_info: PdfInfo, gv_dict: dict):
        file_name = unicodedata.normalize('NFKC', pdf_info.gsutil_uri)
        # 結合文字（濁点）が混在によりエンコードエラーになったため、基底文字と濁点・半濁点を結合（unicodedata.normalize）をする
        predicts = []
        for k, v in gv_dict.items():
            # GPTがnullを返した場合（Python上ではNone）はスキップする
            if v is None:
                continue

            predict = {
                "filename": file_name,
                "entity": unicodedata.normalize('NFKC', k),
                "score": 0.0,
                "content": unicodedata.normalize('NFKC', str(v)),
                "start": 0,
                "end": 0
            }
            logger.info(predict)

            # GrowthVerseエンティティ抽出APIは、「関連書類の文書名」のキー名が"related_contract_name"で返される。
            # 設計書では、"related_contract"となっている。
            # https://lbsk.backlog.com/file/PURPLE_PJ/90.%E5%8F%82%E8%80%83%E8%B3%87%E6%96%99/Growth%20Verse/
            # conpass側では、関連契約書名のキー名は"related_contract"としているため、"related_contract_name"の状態では
            # メタ情報の関連契約書名に追加されないため、キー名を"related_contract"に変換する。
            if predict["entity"] == "related_contract_name":
                predict["entity"] = "related_contract"

            # GrowthVerseエンティティ抽出APIは、「反社条項の有無」のキー名が"antisocialProvisions"で返される。
            # conpass側では、反社条項の有無のキー名は"antisocial"としているため、"antisocialProvisions"の状態では
            # メタ情報の反社条項の有無に追加されないため、キー名を"antisocial"に変換する。
            if predict["entity"] == "antisocialProvisions":
                predict["entity"] = "antisocial"

            if predict["content"]:
                predicts.append(predict)
        return predicts

    def get_predict(self, gcs_files, conpass_contract_type, contract_id) -> GvPredictionResultFormat:
        cloudstorage = GoogleCloudStorage()
        client, bucket = cloudstorage.get_cloudstorage()
        contract_service = ContractService()
        if self.gv_ocr_gemini_endpoint:
            ocr_token = id_token.fetch_id_token(Request(), self.gv_ocr_gemini_endpoint)
        entity_token = id_token.fetch_id_token(Request(), self.gv_entity_extraction_gpt_endpoint)
        lease_token = id_token.fetch_id_token(Request(), self.gv_lease_identification_gpt_endpoint)
        predictfiles = []
        for file in gcs_files:
            signed_url = GvUtils.generate_signed_url_v4(file.url)
            pdf_blob = cloudstorage.get_blob(file.url, bucket)
            pdf_info = self._get_pdf_info(pdf_blob)
            pdf_uri= pdf_info.gsutil_uri
            try:
                # vision APIでテキスト抽出を行う
                logger.info(f"execute vision api : page_size={pdf_info.page_size}")
                if pdf_info.page_size <= 30:
                    logger.info("30P以下の処理の開始")
                    text = self.vision_service.get_pdf_text_for_sync(pdf_info)
                else:
                    logger.info("31P以上の処理の開始")
                    text = self.google_cloud_vision.scan_pdf(pdf_info.blob_name)

                # GrowthVerse APIでエンティティ抽出を行う
                headers = {
                    'Authorization': f'Bearer {entity_token}',
                    'Content-Type': 'application/json'
                }
                body = {
                    'signed_url': signed_url,
                    'contract_type': self._get_conpass_contract_type_by_name(conpass_contract_type),
                    'contract_body': text
                }
                req_id = generate_random_string(10)
                dumpRequest(req_id, self.gv_entity_extraction_gpt_endpoint, 'POST', headers, body)
                response = requests.post(url=self.gv_entity_extraction_gpt_endpoint, headers=headers, data=json.dumps(body), timeout=900)
                dumpResponse(req_id, response.status_code, response.text)
                if response.status_code < 200 or response.status_code >= 300:
                    err_msg = f"Error: growth verse api received non-success status code {response.status_code}"
                    logger.error(err_msg)
                    # GrowthVerse エンティティ抽出APIに失敗をした場合はAzurePredictでエンティティ抽出を行う
                    azure_predict = AzurePredict()
                    predicts = azure_predict.get_predict_from_text(pdf_info, text)
                else:
                    response_body = json.loads(response.text)
                    # response_bodyをAzurePredictの場合の戻り値に合わせた形式に変換をする
                    predicts = self._to_predicts(pdf_info, response_body)

                title=GvPredict.get_meta_value(predicts, 'title')
                logger.info(f"title: {title}")
                lease_keywords=list(LeaseKey.objects.values_list('name', flat=True))
                headers = {
                    'Authorization': f'Bearer {lease_token}',
                    'Content-Type': 'application/json; charset=UTF-8'
                }

                body ={
                    'contract_body': text,
                    'keywords':lease_keywords,
                    'title': title
                }
                req_id = generate_random_string(10)
                dumpRequest(req_id, self.gv_lease_identification_gpt_endpoint, 'POST', headers, body)
                response = requests.post(url=self.gv_lease_identification_gpt_endpoint, headers=headers,data=json.dumps(body), timeout=900)
                dumpResponse(req_id, response.status_code, response.text)
                if response.status_code == 200:
                    response_body = json.loads(response.text)
                    logger.info(f'response_body of semantic matching: {response_body} ')
                    if len(response_body):
                        matched_keyword_list = [item['keyword'] for item in response_body]
                        contract_service.handle_identify_lease_semantic_match(contract_id, matched_keyword_list)
                else:
                    logger.info(f"Error in identifying lease. Code- {response.status_code} - {response.text}")

                # GrowthVerse gemini APIのエンドポイントが設定されている場合、
                # かつページ数が100ページ以下の場合はgeminiAPIを使用して全文抽出を行う
                if self.gv_ocr_gemini_endpoint and pdf_info.page_size <= 100:
                    logger.info(f"execute ocr gemini api : page_size={pdf_info.page_size}")
                    # GrowthVerse APIで全文抽出を行う
                    headers = {
                        'Authorization': f'Bearer {ocr_token}',
                        'Content-Type': 'application/json; charset=UTF-8'
                    }
                    body = {
                        'pdf_uri': pdf_uri,
                        'pdf_size': pdf_info.page_size

                    }
                    req_id = generate_random_string(10)
                    dumpRequest(req_id, self.gv_ocr_gemini_endpoint, 'POST', headers, body)
                    response = requests.post(url=self.gv_ocr_gemini_endpoint, headers=headers, data=json.dumps(body), timeout=900)
                    dumpResponse(req_id, response.status_code, response.text)
                    if response.status_code < 200 or response.status_code >= 300:
                        err_msg = f"Error: Received non-success status code {response.status_code}"
                        logger.error(err_msg)
                        raise Exception(err_msg)
                    else:
                        response_body = json.loads(response.text)
                        text = response_body['ocr_results']

                # predictions: エンティティ抽出APIで取得したメタ情報
                # body: geminiで抽出したテキスト（100ページ以内の場合）、visionで抽出したテキスト（101ページ以上の場合）
                # pdf_page_size: PDFファイルのページ数
                predictfiles.append({"predictions": predicts, "body": text, "pdf_page_size": pdf_info.page_size})

            except Exception as e:
                err_msg = f"execute request error: {e}"
                logger.error(err_msg)
                raise Exception(err_msg)

        serializer = PredictionListSerializer(data={"files": predictfiles})
        if not serializer.is_valid():
            logger.error(serializer.errors)
            raise Exception("解析に失敗しました")

        return serializer.validated_data
