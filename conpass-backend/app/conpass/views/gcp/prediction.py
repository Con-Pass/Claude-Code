from logging import getLogger

from conpass.models import File
from conpass.services.azure.azure_prediction import AzurePredict, PredictionRequestFile
from conpass.services.growth_verse.gv_prediction import GvPredict, GvPredictionRequestFile

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from django.conf import settings

from conpass.views.gcp.serializer.cloud_predict_serializer import GoogleCloudPredictionRequestSerializer

logger = getLogger(__name__)


class GoogleCloudPredictionView(APIView):

    def get(self, request):
        """
        １つのpdfファイルを解析する
        解析結果をarticle libraryに登録する
        契約書（contract）と紐付けがある場合はする
        """
        req_serializer = GoogleCloudPredictionRequestSerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        id = req_serializer.data.get('id')
        user = self.request.user

        wheres = {
            'status': File.Status.ENABLE.value,
            'id': id,
            'account': user.account_id
        }
        file = File.objects.filter(**wheres).get()
        try:
            if settings.GV_ENTITY_EXTRACTION_GPT_ENDPOINT:
                request_file = GvPredictionRequestFile()
                prediction = GvPredict()
            else:
                request_file = PredictionRequestFile()
                prediction = AzurePredict()
            request_file.id = file.id
            request_file.url = file.url
            results = prediction.get_predict(gcs_files=[request_file])
        except Exception as e:
            logger.error(e)
            return Response("pdfの解析に失敗しました。", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(results, status=status.HTTP_200_OK)
