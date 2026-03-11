import datetime

import factory.django
from django.utils.timezone import make_aware
from faker import Faker

from conpass.models import WorkflowTask
from conpass.models.constants.statusable import Statusable
from conpass.tests.factories.workflow_task_master import WorkflowTaskMasterFactory
from conpass.tests.factories.workflow_step import WorkflowStepFactory

faker = Faker(locale='ja_JP')


class WorkflowTaskFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WorkflowTask

    name = factory.Sequence(lambda n: f"ワークフロータスク名{n}")
    step = factory.SubFactory(WorkflowStepFactory)
    task = factory.SubFactory(WorkflowTaskMasterFactory)
    is_finish = False
    finish_condition = WorkflowTask.FinishCondition.ALL.value
    author_notify = WorkflowTask.AuthorNotifyCondition.FALSE.value
    status = Statusable.Status.ENABLE.value
    created_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    updated_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
