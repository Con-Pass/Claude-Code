import json
from django.test import TestCase
from unittest.mock import patch

from conpass.models import User
from conpass.tests.factories.account import AccountFactory

from rest_framework.test import APIClient
from rest_framework_jwt.serializers import jwt_payload_handler
from rest_framework_jwt.settings import api_settings
from rest_framework_jwt.utils import jwt_encode_handler


class TestPasswordReset(TestCase):
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

    @patch('sendgrid.SendGridAPIClient.send')
    def test_password_reset__成功(self, mock_send):
        response = self.client.post('/api/password_reset_mail/', json.dumps({
            'params': {
                'email': self.user.login_name,
            }
        }), content_type='application/json')
        assert mock_send.called
        assert response.status_code == 200

    def test_password_reset_不正なemail__失敗(self):
        response = self.client.post('/api/password_reset_mail/', json.dumps({
            'params': {
                'email': 'test@example.com',
            }
        }), content_type='application/json')
        assert response.status_code == 400
