import json
import datetime
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch

from conpass.models import User
from conpass.models.login_failure import LoginFailure
from conpass.tests.factories.account import AccountFactory

from rest_framework.test import APIClient
from rest_framework_jwt.serializers import jwt_payload_handler
from rest_framework_jwt.settings import api_settings
from rest_framework_jwt.utils import jwt_encode_handler


class TestLogin(TestCase):
    def setUp(self):
        account = AccountFactory()
        self.user = User.objects.create_user(
            login_name='unittest@example.com',
            password='secret',
            type=User.Type.ACCOUNT.value,
            account=account
        )

        self.client = APIClient()
        self.client.login(login_name='unittest@example.com', password='secret')
        payload = jwt_payload_handler(self.user)
        token = jwt_encode_handler(payload)
        self.client.cookies[api_settings.JWT_AUTH_COOKIE] = token

    def test_post__login__成功(self):
        response = self.client.post('/api/auth/login', json.dumps({
            'login_name': self.user.login_name,
            'password': 'secret'
        }), content_type='application/json')
        assert response.status_code == 200

    def test_post__login__パスワードが不正_失敗(self):
        response = self.client.post('/api/auth/login', json.dumps({
            'login_name': self.user.login_name,
            'password': 'aaa'
        }), content_type='application/json')
        assert response.status_code == 400
        assert response.data['error_message'] == 'idかパスワードが間違っています。'

    def test_post__login__5回連続パスワードが不正_失敗(self):
        for _ in range(LoginFailure.LOCK_ATTEMPTS_COUNT + 1):
            response = self.client.post('/api/auth/login', json.dumps({
                'login_name': self.user.login_name,
                'password': 'aaa'
            }), content_type='application/json')
        assert response.status_code == 400
        assert response.data['error_message'] == '一時的にロックされています。5分後に再試行してください。'

    def test_post__login__5回連続パスワードが不正が5回続く_失敗(self):
        for _ in range(LoginFailure.FLL_LOCK_ATTEMPTS_COUNT + 1):
            for _ in range(LoginFailure.LOCK_ATTEMPTS_COUNT):
                self.client.post('/api/auth/login', json.dumps({
                    'login_name': self.user.login_name,
                    'password': 'aaa'
                }), content_type='application/json')

            # 5分後に進める
            with patch('django.utils.timezone.now',
                       return_value=timezone.now() + datetime.timedelta(minutes=LoginFailure.LOCK_TIME)):
                # 5分後にもう一度ログインを試みる
                response = self.client.post('/api/auth/login', json.dumps({
                    'login_name': self.user.login_name,
                    'password': 'aaa'
                }), content_type='application/json')

        assert response.status_code == 400
        assert response.data['error_message'] == 'アカウントが完全にロックされました。パスワードを変更してください。'
