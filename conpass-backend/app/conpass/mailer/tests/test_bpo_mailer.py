from unittest import mock

import pytest

from conpass.mailer.bpo_mailer import BpoMailer
from conpass.tests.factories.bporequest import BPORequestFactory
from conpass.tests.factories.user import UserFactory


@pytest.fixture
def bpo_mailer():
    with mock.patch('conpass.mailer.bpo_mailer.BpoMailer.send'):
        yield BpoMailer()


class TestBpoMailer:

    @pytest.mark.django_db
    def test__send_user_request_mail(self, bpo_mailer: BpoMailer):
        user = UserFactory()
        bpo = BPORequestFactory()
        BpoMailer().send_user_request_mail(user, bpo)

        # TODO: メール本文のテスト
        assert 1 == bpo_mailer.send.call_count

    @pytest.mark.django_db
    def test__send_admin_request_mail(self, bpo_mailer: BpoMailer):
        user = UserFactory()
        bpo = BPORequestFactory()
        BpoMailer().send_admin_request_mail(user, bpo)

        # TODO: メール本文のテスト
        assert 1 == bpo_mailer.send.call_count
