import json

from rest_framework.response import Response
from rest_framework.views import APIView


class TemplateJsonView(APIView):
    """
    テンプレート変数定義情報取得
    """

    def get(self, request):
        with open("conpass/views/template_json/template.json", "r") as file:
            template_data = json.load(file)

        return Response(data=template_data)
