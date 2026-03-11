from unittest import mock

import pytest

from conpass.mailer.support_mailer import SupportMailer
from conpass.tests.factories.support import SupportFactory
from conpass.tests.factories.user import UserFactory


@pytest.fixture
def support_mailer():
    with mock.patch('conpass.mailer.support_mailer.SupportMailer.send'):
        yield SupportMailer()


class TestBpoMailer:

    @pytest.mark.django_db
    def test__send_user_request_mail(self, support_mailer: SupportMailer):
        user = UserFactory()
        support = SupportFactory()
        SupportMailer().send_user_request_mail(user, support)

        # TODO: メール本文のテスト
        assert 1 == support_mailer.send.call_count

    @pytest.mark.django_db
    def test__send_admin_request_mail(self, support_mailer: SupportMailer):
        user = UserFactory()
        support = SupportFactory()
        SupportMailer().send_admin_request_mail(user, support)

        # TODO: メール本文のテスト
        assert 1 == support_mailer.send.call_count
