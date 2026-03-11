import time
from logging import getLogger

from django.http import HttpRequest
from django.core.management import call_command
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.services.contract.contract_upload_prediction_task import prediction_on_upload_task_execute, \
    zip_upload_task_execute, classify_by_qr_code_presence_task_execute
from internal_api.views.tasks.contract_upload_prediction_task.contract_upload_prediction_task_serializer \
    import PrivateApiExecutePredictionOnUploadTaskRequestBodySerializer, PrivateApiExecuteZipUploadTaskRequestBodySerializer, \
    PrivateApiExecuteClassifyByQrcodePresenceTaskRequestBodySerializer

logger = getLogger(__name__)


class PrivateApiExecutePredictionOnUploadTaskView(APIView):
    permission_classes = []

    def post(self, request):
        req_serializer = PrivateApiExecutePredictionOnUploadTaskRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data

        predict_file_id = data.get('predictFileId')
        predict_file_url = data.get('predictFileUrl')
        contract_id = data.get('contractId')
        user_id = data.get('userId')
        datatype = data.get('datatype')
        conpass_contract_type = data.get('conpassContractType')
        is_meta_check = data.get('isMetaCheck')
        renew_notify = data.get('renewNotify')
        upload_id = data.get('uploadId')

        ret = prediction_on_upload_task_execute(
            predict_file_id,
            predict_file_url,
            contract_id,
            user_id,
            datatype,
            conpass_contract_type,
            is_meta_check,
            renew_notify,
            upload_id,
        )

        return Response(ret)


class PrivateApiExecuteZipUploadTaskView(APIView):
    permission_classes = []

    def post(self, request):
        req_serializer = PrivateApiExecuteZipUploadTaskRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data

        zip_file_path = data.get('zipFilePath')
        bucket_type = data.get('bucketType')
        user_id = data.get('userId')
        conpass_contract_type = data.get('conpassContractType')
        directory_id = data.get('directoryId')
        is_provider = data.get('isProvider')
        is_open = data.get('isOpen')
        description = data.get('description')
        is_meta_check = data.get('isMetaCheck')
        renew_notify = data.get('renewNotify')
        upload_id = data.get('uploadId')

        ret = zip_upload_task_execute(
            zip_file_path,
            bucket_type,
            user_id,
            conpass_contract_type,
            directory_id,
            is_provider,
            is_open,
            description,
            is_meta_check,
            renew_notify,
            upload_id,
        )

        return Response(ret)


class PrivateApiClassifyByQrcodePresenceTaskView(APIView):
    permission_classes = []

    def post(self, request):
        req_serializer = PrivateApiExecuteClassifyByQrcodePresenceTaskRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data

        zip_upload_id = data.get('zipUploadId')
        pdf_upload_id = data.get('pdfUploadId')
        user_id = data.get('userId')
        conpass_contract_type = data.get('conpassContractType')
        directory_id = data.get('directoryId')

        ret = classify_by_qr_code_presence_task_execute(
            zip_upload_id,
            pdf_upload_id,
            user_id,
            conpass_contract_type,
            directory_id,
        )

        return Response(ret)
