import datetime
import random

import factory.django
from django.utils.timezone import make_aware
from faker import Faker

from conpass.models import WorkflowTaskMaster
from conpass.models.constants.statusable import Statusable

faker = Faker(locale='ja_JP')


class WorkflowTaskMasterFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WorkflowTaskMaster

    name = factory.Sequence(lambda n: f"タスク名{n}")
    description = factory.Sequence(lambda n: f"タスク内容{n}")
    type = WorkflowTaskMaster.Type.COMMON.value
    is_need_contract = False
    status = Statusable.Status.ENABLE.value
    created_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    updated_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
