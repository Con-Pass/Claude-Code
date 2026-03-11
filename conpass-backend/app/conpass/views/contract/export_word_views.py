import os
import traceback
from logging import getLogger

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

import base64

from conpass.views.contract.serializer.export_word_serializer import ContractExportWordRequestBodySerializer
from conpass.services.contract.contract_service import ContractService

logger = getLogger(__name__)


class ExportWordView(APIView):

    def post(self, request):
        # request
        req_serializer = ContractExportWordRequestBodySerializer(data=request.data["params"])
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        title = req_serializer.data.get('title')
        body = req_serializer.data.get('body')
        seq = req_serializer.data.get('id')
        qr = req_serializer.data.get('qr')
        contract_service = ContractService()

        if not qr:
            seq = None

        try:
            word = contract_service.create_word(title, body, seq)
            with open(word, 'rb') as fsrc:
                b64 = base64.b64encode(fsrc.read())
            os.remove(word)
            return Response(b64, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"message": "docxファイルの生成に失敗しました。"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
