import datetime

import factory.django
from django.utils.timezone import make_aware
from faker import Faker

from conpass.models import Workflow
from conpass.tests.factories.account import AccountFactory
from conpass.tests.factories.contract import ContractFactory
from conpass.tests.factories.client import ClientFactory

faker = Faker(locale='ja_JP')


class WorkflowFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Workflow

    name = factory.Sequence(lambda n: f"ワークフロー名{n}")
    account = factory.SubFactory(AccountFactory)
    contract = factory.SubFactory(ContractFactory)
    renewal_from_contract = None
    client = factory.SubFactory(ClientFactory)
    current_step_id = 1
    type = Workflow.Type.WORKFLOW.value
    is_rejected = False
    memo = factory.Sequence(lambda n: f"備考{n}")
    template = None
    status = Workflow.Status.ENABLE.value
    created_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    updated_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
