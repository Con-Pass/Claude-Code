from unittest import mock

import pytest

from conpass.mailer.workflow_mailer import WorkflowMailer
from conpass.tests.factories.workflow_task import WorkflowTaskFactory
from conpass.tests.factories.user import UserFactory


@pytest.fixture
def workflow_mailer():
    with mock.patch('conpass.mailer.workflow_mailer.WorkflowMailer.send'):
        yield WorkflowMailer()


class TestWorkflowMailer:

    @pytest.mark.django_db
    def test__send_user_request_mail(self, workflow_mailer: WorkflowMailer):
        user = UserFactory()
        workflow_task = WorkflowTaskFactory()
        WorkflowMailer().send_next_task_request_mail(user, workflow_task)

        # TODO: メール本文のテスト
        assert 1 == workflow_mailer.send.call_count
