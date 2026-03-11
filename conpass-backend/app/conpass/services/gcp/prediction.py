import dataclasses
import io
import unicodedata
from typing import List, Union

import pikepdf
import dataclasses_json
from google.api_core.client_options import ClientOptions
from google.cloud import automl_v1

from django.conf import settings
from google.cloud.automl_v1 import ExamplePayload, TextSnippet
from google.cloud.storage import Blob

from common.utils import iter_utils
from .cloud_storage import GoogleCloudStorage
from logging import getLogger

from .dto.pdf_info import PdfInfo
from .serializer.prediction_serializer import PredictionListSerializer
from .vision import GoogleCloudVision
from .vision_service import VisionService

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


class PredictionResultFormat:
    # １つ目のリストはファイル単位
    files: [Predictions]


@dataclasses_json.dataclass_json
@dataclasses.dataclass
class PredictionRequestFile:
    id: int
    url: str


class GoogleCloudPredict():

    def __init__(self):
        self.model_name = settings.GCP_PREDICTION_MODEL_NAME
        self.vision_service = VisionService()
        self.google_cloud_vision = GoogleCloudVision()

    def inline_text_payload(self, file_path):
        """
        ファイル読み取り用のペイロード
        ローカル環境用
        """
        with open(file_path, 'rb') as ff:
            content = ff.read()
        return {'text_snippet': {'content': content, 'mime_type': 'text/plain'}}

    def pdf_payload(self, file_path: str):
        """
        PDF用のペイロード
        GCS
        """
        return {'document': {'input_config': {'gcs_source': {'input_uris': [file_path]}}}}

    def _get_prediction_request(self, payload: Union[dict, ExamplePayload]):
        """
        predictionのクライアントを取得する
        """
        options = ClientOptions(api_endpoint='automl.googleapis.com')
        prediction_client = automl_v1.PredictionServiceClient(client_options=options)

        params = {}
        # predict内で例外が発生した場合はMAX_PREDICT_RETRY_COUNTの回数までリトライを行う
        for i in range(MAX_PREDICT_RETRY_COUNT + 1):
            try:
                request = prediction_client.predict(name=self.model_name, payload=payload, params=params)
                break
            except Exception as e:
                logger.info(f'predict error: retry count=[{i}]')
                if i == MAX_PREDICT_RETRY_COUNT:
                    logger.error(e)
                    raise e
        return request  # waits until request is returned

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
                if pdf_info.page_size <= 5:
                    predict_file = self._get_predict_file_5_page_or_less(pdf_info)
                elif 6 <= pdf_info.page_size <= 30:
                    predict_file = self._get_predict_file_6_page_or_more_and_30_page_or_less(pdf_info)
                else:
                    predict_file = self._get_predict_file_31_page_or_more(pdf_info)

                predictfiles.append(predict_file)
            except Exception as e:
                logger.error(e)
                raise e

        serializer = PredictionListSerializer(data={"files": predictfiles})
        if not serializer.is_valid():
            raise Exception("解析に失敗しました")

        return serializer.validated_data

    def _get_predict_file_5_page_or_less(self, pdf_info: PdfInfo):
        """5P以下の場合Predict(引数: PDFファイル)でエンティティ抽出する"""

        rq = self._get_prediction_request(self.pdf_payload(pdf_info.gsutil_uri))
        body = rq.preprocessed_input.document.document_text.content
        predicts = []
        for annotation_payload in rq.payload:
            predict = self._to_predict(pdf_info, annotation_payload)
            predicts.append(predict)
        return {"predictions": predicts, "body": body}

    def _get_predict_file_6_page_or_more_and_30_page_or_less(self, pdf_info: PdfInfo):
        """
        6P以上30P以下の場合、VisionAPI OCRで全文取得してからPredict(引数: テキスト)でエンティティ抽出する
        エンティティの抽出を同期処理で実行する場合、最大10,000文字の制約があるため分割して実行する
        """
        text = self.vision_service.get_pdf_text_for_sync(pdf_info)
        return self._get_predict_file_per_10000(pdf_info, text)

    def _get_predict_file_31_page_or_more(self, pdf_info: PdfInfo):
        """31P以上の場合Predict(引数: テキスト)でエンティティ抽出する"""
        text = self.google_cloud_vision.scan_pdf(pdf_info.blob_name)
        return self._get_predict_file_per_10000(pdf_info, text)

    def _get_predict_file_per_10000(self, pdf_info: PdfInfo, text: str):
        predicts = []
        for parted_text in iter_utils.iterable_split(text, 10_000):
            snippet = TextSnippet(content=parted_text, mime_type="text/plain")
            rq = self._get_prediction_request(ExamplePayload(text_snippet=snippet))
            for annotation_payload in rq.payload:
                predict = self._to_predict(pdf_info, annotation_payload)
                predicts.append(predict)

        return {"predictions": predicts, "body": text}

    def _to_predict(self, pdf_info: PdfInfo, annotation_payload):
        text_segment = annotation_payload.text_extraction.text_segment

        # 結合文字（濁点）が混在によりエンコードエラーになったため、基底文字と濁点・半濁点を結合（unicodedata.normalize）をする
        predict = {
            "filename": unicodedata.normalize('NFKC', pdf_info.gsutil_uri),
            "entity": unicodedata.normalize('NFKC', annotation_payload.display_name),
            "score": annotation_payload.text_extraction.score,
            "content": unicodedata.normalize('NFKC', text_segment.content.replace('\n', '')),
            "start": text_segment.start_offset,
            "end": text_segment.end_offset
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
