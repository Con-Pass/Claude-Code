import dataclasses
import io
import unicodedata
from typing import List

import pikepdf
import dataclasses_json

from ..gcp.vision import GoogleCloudVision
from ..gcp.vision_service import VisionService

from django.conf import settings
from google.cloud.storage import Blob

from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient

from common.utils import iter_utils
from ..gcp.cloud_storage import GoogleCloudStorage

from ..gcp.dto.pdf_info import PdfInfo
from .serializer.azure_prediction_serializer import PredictionListSerializer

from logging import getLogger

logger = getLogger(__name__)

MAX_PREDICT_RETRY_COUNT = 5


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


class PredictionResultFormat:
    # １つ目のリストはファイル単位
    files: [Predictions]


@dataclasses_json.dataclass_json
@dataclasses.dataclass
class PredictionRequestFile:
    id: int
    url: str


class AzurePredict():
    def __init__(self):
        self.azure_language_endpoint = settings.AZURE_LANGUAGE_ENDPOINT
        self.azure_language_key = settings.AZURE_LANGUAGE_KEY
        self.azure_project_name = settings.CUSTOM_ENTITIES_PROJECT_NAME
        self.azure_deployment_name = settings.CUSTOM_ENTITIES_DEPLOYMENT_NAME
        self.vision_service = VisionService()
        self.google_cloud_vision = GoogleCloudVision()

    def _get_prediction_request(self, payload):
        """
        クライアントを取得する
        """
        text_analytics_client = TextAnalyticsClient(
            endpoint=self.azure_language_endpoint,
            credential=AzureKeyCredential(self.azure_language_key),
        )

        # MAX_PREDICT_RETRY_COUNTまでリトライを行う
        for i in range(MAX_PREDICT_RETRY_COUNT + 1):
            try:
                logger.info("Azure Predictの開始")
                documents = [payload]
                # Text Analytics APIを使用した予測
                response = text_analytics_client.begin_recognize_custom_entities(
                    documents,
                    project_name=self.azure_project_name,
                    deployment_name=self.azure_deployment_name
                )
                logger.info("Azure Predictの終了")
                break
            except Exception as e:
                logger.info(f'predict error: retry count=[{i}]')
                if i == MAX_PREDICT_RETRY_COUNT:
                    logger.error(e)
                    raise e
        return response  # 分析結果を返す

    def get_predict(self, gcs_files: [PredictionRequestFile]) -> PredictionResultFormat:
        """
        predictionで実際に解析を行い、結果をList[Dict]で返す
        FileIdと対象ファイル一覧（GCSのパス）を指定
        """
        cloudstorage = GoogleCloudStorage()

        client, bucket = cloudstorage.get_cloudstorage()

        # モデル／ストレージの入力

        predictfiles = []

        # コメント
        for file in gcs_files:
            pdf_blob = cloudstorage.get_blob(file.url, bucket)
            pdf_info = self._get_pdf_info(pdf_blob)
            try:
                if pdf_info.page_size <= 30:
                    logger.info("30P以下の処理の開始")
                    predict_file = self._get_predict_file_30_page_or_less(pdf_info)
                else:
                    logger.info("31P以上の処理の開始")
                    predict_file = self._get_predict_file_31_page_or_more(pdf_info)

                predictfiles.append(predict_file)
            except Exception as e:
                logger.error(e)
                raise e

        serializer = PredictionListSerializer(data={"files": predictfiles})
        if not serializer.is_valid():
            raise Exception("解析に失敗しました")

        return serializer.validated_data

    def get_predict_from_text(self, pdf_info: PdfInfo, text: str) -> list:
        """
        azure predictionで実際に解析を行い、結果をList[Dict]で返す
        PDFファイルの情報と解析をするテキストを指定する。
        """
        return self._get_predict_file_per_100000(pdf_info, text, True)

    def _get_predict_file_30_page_or_less(self, pdf_info: PdfInfo):
        """
        30P以下の場合、VisionAPI OCRで全文取得してからPredict(引数: テキスト)でエンティティ抽出する
        """

        text = self.vision_service.get_pdf_text_for_sync(pdf_info)
        return self._get_predict_file_per_100000(pdf_info, text)

    def _get_predict_file_31_page_or_more(self, pdf_info: PdfInfo):
        """31P以上の場合Predict(引数: テキスト)でエンティティ抽出する"""
        text = self.google_cloud_vision.scan_pdf(pdf_info.blob_name)
        return self._get_predict_file_per_100000(pdf_info, text)

    def _get_predict_file_per_100000(self, pdf_info: PdfInfo, text: str, predictsOnly: bool = False):
        predicts = []
        for parted_text in iter_utils.iterable_split(text, 100_000):
            rq = self._get_prediction_request(parted_text)
            document_results = rq.result()
            logger.info(f"predict:{document_results}")
            for custom_entities_result in document_results:
                if custom_entities_result.kind == "CustomEntityRecognition":
                    for annotation_payload in custom_entities_result.entities:
                        logger.info(annotation_payload)
                        predict = self._to_predict(pdf_info, annotation_payload)
                        predicts.append(predict)

        return predicts if predictsOnly else {"predictions": predicts, "body": text, "pdf_page_size": pdf_info.page_size}

    def _to_predict(self, pdf_info: PdfInfo, annotation_payload):
        # 結合文字（濁点）が混在によりエンコードエラーになったため、基底文字と濁点・半濁点を結合（unicodedata.normalize）をする
        predict = {
            "filename": unicodedata.normalize('NFKC', pdf_info.gsutil_uri),
            "entity": unicodedata.normalize('NFKC', annotation_payload.category.lower()),
            "score": annotation_payload.confidence_score,
            "content": unicodedata.normalize('NFKC', annotation_payload.text.replace('\n', '')),
            "start": annotation_payload.offset,
            "end": annotation_payload.offset + annotation_payload.length
        }
        logger.info('predict', extra={'info': predict})
        return predict

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

    def save_prediction_to_article_library(self, fileid, predictions: List[PredictionResult]):
        """
        prediction結果をarticle libraryに保存する
        """
        pass
