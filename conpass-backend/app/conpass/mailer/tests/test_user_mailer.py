from unittest import mock

import pytest

from conpass.mailer.user_mailer import UserMailer
from conpass.tests.factories.user import UserFactory


@pytest.fixture
def user_mailer():
    with mock.patch('conpass.mailer.user_mailer.UserMailer.send'):
        yield UserMailer()


class TestUserMailer:

    @pytest.mark.django_db
    def test__send_user_request_mail(self, user_mailer: UserMailer):
        user = UserFactory()
        UserMailer().send_user_create_mail(user)

        # TODO: メール本文のテスト
        assert 1 == user_mailer.send.call_count

    @pytest.mark.django_db
    def test__send_user_modify_mail(self, user_mailer: UserMailer):
        user = UserFactory()
        login_user = UserFactory()
        UserMailer().send_user_modify_mail(user, login_user)

        # TODO: メール本文のテスト
        assert 1 == user_mailer.send.call_count
