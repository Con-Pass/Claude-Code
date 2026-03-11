import datetime

import factory.django
from django.utils.timezone import make_aware
from faker import Faker

from conpass.models import WorkflowStep
from conpass.models.constants.statusable import Statusable
from conpass.tests.factories.workflow import WorkflowFactory

faker = Faker(locale='ja_JP')


class WorkflowStepFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WorkflowStep

    name = factory.Sequence(lambda n: f"ステップ名{n}")
    workflow = factory.SubFactory(WorkflowFactory)  # ワークフローID
    parent_step = None
    child_step = None
    memo = factory.Sequence(lambda n: f"備考{n}")  # 備考
    reject_step_count = 1
    start_date = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    end_date = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    expire_day = 3
    status = Statusable.Status.ENABLE.value
    created_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    updated_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
