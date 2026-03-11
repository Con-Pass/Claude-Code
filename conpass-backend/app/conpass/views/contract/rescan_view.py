from logging import getLogger
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.models import Contract, File, ContractBody
from conpass.models.meta_data import MetaData
from conpass.models.constants.statusable import Statusable
from conpass.services.contract.contract_upload_prediction_task import ContractUploadPredictionService

logger = getLogger(__name__)


class ContractExtractionStatusView(APIView):
    """契約書のテキスト・メタ情報の抽出状況を返す"""

    def get(self, request, contract_id):
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            return Response({'detail': '契約書が見つかりません'}, status=status.HTTP_404_NOT_FOUND)

        has_body = ContractBody.objects.filter(
            contract=contract,
            status=Statusable.Status.ENABLE.value,
        ).exists()
        meta_count = MetaData.objects.filter(
            contract=contract,
            status=Statusable.Status.ENABLE.value,
        ).count()

        return Response({'hasBody': has_body, 'metaCount': meta_count})


class ContractRescanView(APIView):
    """既存契約書ファイルのテキスト・メタ情報を再抽出する"""

    def post(self, request, contract_id):
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            return Response({'detail': '契約書が見つかりません'}, status=status.HTTP_404_NOT_FOUND)

        # 有効なPDFファイルを取得（ETCを除く）
        files = list(
            contract.file
            .filter(status=File.Status.ENABLE.value)
            .exclude(type=File.Type.ETC.value)
        )
        pdf_files = [f for f in files if f.url.lower().endswith('.pdf') or f.name.lower().endswith('.pdf')]

        if not pdf_files:
            return Response({'detail': 'PDFファイルが見つかりません'}, status=status.HTTP_400_BAD_REQUEST)

        file = pdf_files[-1]  # 最新ファイルを使用

        try:
            # GvPredict経由で抽出（ローカルでは_local_get_predictが使われる）
            if settings.GV_ENTITY_EXTRACTION_GPT_ENDPOINT:
                from conpass.services.growth_verse.gv_prediction import GvPredict, GvPredictionRequestFile
                predict_file = GvPredictionRequestFile(file.id, file.url)
                prediction = GvPredict()
                prediction_result = prediction.get_predict(
                    gcs_files=[predict_file],
                    conpass_contract_type='その他',
                    contract_id=contract.id,
                )
            else:
                from conpass.services.azure.azure_prediction import AzurePredict, PredictionRequestFile
                predict_file = PredictionRequestFile(file.id, file.url)
                prediction = AzurePredict()
                prediction_result = prediction.get_predict(gcs_files=[predict_file])

            # 抽出テキストの品質チェック（失敗時は既存データを保持してエラー返却）
            extracted_body = (prediction_result.get('files') or [{}])[0].get('body', '')
            _EXTRACTION_FAILURE_SENTINEL = '（テキスト抽出なし）'
            if not extracted_body or extracted_body.strip() == _EXTRACTION_FAILURE_SENTINEL:
                logger.warning(f'[Rescan] OCR failed for contract_id={contract_id}, keeping existing data')
                return Response(
                    {'detail': 'テキスト抽出に失敗しました。ファイルが画像PDFの場合はOCR処理に時間がかかることがあります。しばらく待ってから再試行してください。'},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

            # 既存データを削除（重複回避）
            MetaData.objects.filter(contract=contract).delete()
            ContractBody.objects.filter(contract=contract).delete()

            # 新しい抽出結果を保存
            service = ContractUploadPredictionService()
            # AIが分類した文書種別を使用（ローカルフォールバック時は prediction_result に含まれる）
            doc_type = prediction_result.get('document_type', 'その他')
            service.create_meta_data_type(contract, request.user, doc_type)
            service.create_meta_data(prediction_result, contract, request.user)
            service.create_contract_body(prediction_result, contract, request.user)

            return Response({'detail': '再抽出完了'}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f'[Rescan] error for contract_id={contract_id}: {e}')
            return Response(
                {'detail': f'再抽出に失敗しました: {str(e)[:200]}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
