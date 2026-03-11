from logging import getLogger

from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.views.anyflow.serializer.anyflow_serializer import UserIDResponseBodySerializer
from conpass.models import User

logger = getLogger(__name__)


class UserInfoView(APIView):
    def get(self, request):
        user_id = self.request.user.id

        wheres = {
            'pk': user_id,
            'type': User.Type.ACCOUNT.value,
            'is_bpo': False,
            'status': User.Status.ENABLE.value,
        }

        try:
            user = User.objects.filter(**wheres).get()
            res_serializer = UserIDResponseBodySerializer(user)
            return Response(data=res_serializer.data)
        except User.DoesNotExist:
            return Response(data={})
