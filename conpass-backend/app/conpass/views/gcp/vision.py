from logging import getLogger

from celery.result import AsyncResult

from conpass.models import File
from conpass.services.gcp.vision import GoogleCloudVision

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from conpass.tasks import vision_scan_pdf_task
from conpass.views.gcp.serializer.cloud_vision_serializer import GoogleCloudVisionRequestSerializer

logger = getLogger(__name__)


class GoogleCloudVisionImageView(APIView):

    def get(self, request):
        """
        １つの画像ファイルをVisonで読み取ってテキストにする
        file連携なのでid指定
        """
        req_serializer = GoogleCloudVisionRequestSerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        id = req_serializer.data.get('id')
        name = req_serializer.data.get('path')

        if id and not name:
            wheres = {
                'id': id,
                'status': File.Status.ENABLE.value,
            }
            file = File.objects.filter(**wheres).get()
            name = file.url

        vision = GoogleCloudVision()
        result = vision.scan_image(filename=name)

        return Response(result, status=status.HTTP_200_OK)


class GoogleCloudVisionPdfView(APIView):

    def get(self, request):
        """
        １つのpdfファイルをVisonで読み取ってテキストにする
        file連携なのでid指定
        """
        req_serializer = GoogleCloudVisionRequestSerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        id = req_serializer.data.get('id')
        name = req_serializer.data.get('path')

        if id and not name:
            wheres = {
                'id': id,
                'status': File.Status.ENABLE.value,
            }
            file = File.objects.filter(**wheres).get()
            name = file.url

        task_id: AsyncResult = vision_scan_pdf_task.delay(filename=name)
        return Response(data={
            'task_id': task_id.task_id
        }, status=status.HTTP_200_OK)
        # 同期でやる場合
        # vision = GoogleCloudVision()
        # result = vision.scan_pdf(filename=file)
        # return Response(result, status=status.HTTP_200_OK)
