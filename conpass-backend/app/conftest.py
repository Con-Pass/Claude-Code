import pytest
from rest_framework.test import APIClient
from rest_framework_jwt.serializers import jwt_payload_handler
from rest_framework_jwt.settings import api_settings
from rest_framework_jwt.utils import jwt_encode_handler

from common.auth.authentication import SYS_COOKIE_NAME
from conpass.models import User
from conpass.tests.factories.account import AccountFactory


@pytest.fixture
def login_user():
    account = AccountFactory()
    return User.objects.create_user(
        login_name='unittest@example.com',
        password='secret',
        type=User.Type.ACCOUNT.value,
        account=account
    )


@pytest.fixture
def api_client(login_user):
    client = APIClient()
    client.login(login_name='unittest@example.com', password='secret')
    payload = jwt_payload_handler(login_user)
    token = jwt_encode_handler(payload)
    client.cookies[api_settings.JWT_AUTH_COOKIE] = token
    return client


@pytest.fixture
def login_admin():
    account = AccountFactory()
    return User.objects.create_user(
        login_name='admin@example.com',
        password='secret',
        type=User.Type.ADMIN.value,
        account=account
    )


@pytest.fixture
def sys_client(login_admin):
    client = APIClient()
    client.login(login_name='admin@example.com', password='secret')
    payload = jwt_payload_handler(login_admin)
    token = jwt_encode_handler(payload)
    client.cookies[SYS_COOKIE_NAME] = token
    return client
