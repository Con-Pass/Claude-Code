from unittest import mock

import pytest

from conpass.mailer.bpo_correction_mailer import BpoCorrectionMailer
from conpass.tests.factories.bporequest import BPORequestFactory
from conpass.tests.factories.user import UserFactory


@pytest.fixture
def bpo_correction_mailer():
    with mock.patch('conpass.mailer.bpo_correction_mailer.BpoCorrectionMailer.send'):
        yield BpoCorrectionMailer()


class TestBpoCorrectionMailer:

    @pytest.mark.django_db
    def test__send_user_request_mail(self, bpo_correction_mailer: BpoCorrectionMailer):
        user = UserFactory()
        mail_body = ''
        for i in range(3):
            body = f"契約書ID: {i}\n契約書詳細画面: https://www.con-pass.jp/contract/{i}\n"
            mail_body += "\n" + body
        BpoCorrectionMailer().send_user_request_mail(user, 'データ補正', 'データ補正', mail_body)

        # TODO: メール本文のテスト
        assert 1 == bpo_correction_mailer.send.call_count

    @pytest.mark.django_db
    def test__send_admin_request_mail(self, bpo_correction_mailer: BpoCorrectionMailer):
        user = UserFactory()
        mail_body = ''
        for i in range(3):
            body = f"契約書ID: {i}\n契約書詳細画面: https://www.con-pass.jp/contract/{i}\n"
            mail_body += "\n" + body
        BpoCorrectionMailer().send_admin_request_mail(user, 'データ補正', 'データ補正', mail_body)

        # TODO: メール本文のテスト
        assert 1 == bpo_correction_mailer.send.call_count
