from logging import getLogger

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings

from conpass.tasks import add_execute, vision_scan_pdf_task_execute, prediction_task_execute
from conpass.services.azure.azure_prediction import PredictionRequestFile
from conpass.services.growth_verse.gv_prediction import GvPredictionRequestFile
from internal_api.views.tasks.conpass.conpass_serializer import PrivateApiExecuteAddRequestBodySerializer, \
    PrivateApiExecuteVisionScanPdfTaskRequestBodySerializer, PrivateApiExecutePredictionTaskRequestBodySerializer

logger = getLogger(__name__)


class PrivateApiExecuteAdd(APIView):
    permission_classes = []

    def post(self, request):
        req_serializer = PrivateApiExecuteAddRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data

        x = data.get('x')
        y = data.get('y')

        ret = add_execute(x, y)

        return Response({'result': ret})


class PrivateApiExecuteVisionScanPdfTaskView(APIView):
    permission_classes = []

    def post(self, request):
        """
        GoogleCloudVisionを使って、PDFファイルの本文を（画像として）スキャンし、テキスト化する
        """
        req_serializer = PrivateApiExecuteVisionScanPdfTaskRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data

        filename = data.get('filename')
        contract_id = data.get('contractId')
        user_id = data.get('userId')

        ret = vision_scan_pdf_task_execute(filename, contract_id, user_id)

        return Response({'result': ret})


class PrivateApiExecutePredictionTaskView(APIView):
    permission_classes = []

    def post(self, request):
        """
        GoogleCloudPredictionを使って、PDFファイルの本文からメタ情報を抽出します
        """
        req_serializer = PrivateApiExecutePredictionTaskRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data

        id = data.get('id')
        url = data.get('url')

        file = GvPredictionRequestFile() if settings.GV_ENTITY_EXTRACTION_GPT_ENDPOINT else PredictionRequestFile()
        file.id = id
        file.url = url
        ret = prediction_task_execute(file)

        return Response({'result': ret})
