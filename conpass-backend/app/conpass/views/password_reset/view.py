import string
import random
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import transaction
from django.contrib.auth.hashers import make_password
from conpass.mailer.password_reset_mailer import PasswordRestMailer
from conpass.models import User
from conpass.models.login_failure import LoginFailure


def generate_password(length=15):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


class PasswordResetMailView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        params = request.data.get('params')
        try:
            user = User.objects.get(login_name=params['email'])
        except User.DoesNotExist:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        new_password = generate_password()
        user.password = make_password(new_password)
        user.save()

        # ログイン失敗履歴削除
        LoginFailure.objects.filter(email=user.login_name).delete()

        try:
            mailer = PasswordRestMailer()
            mailer.send_password_reset_mail(user, new_password)
        except Exception as e:
            raise e

        return Response({"message": "メールを送信しました"}, status=status.HTTP_200_OK)
