import datetime
import random

import factory
from django.utils.timezone import make_aware
from faker import Faker

from conpass.models import Contract
from conpass.tests.factories.account import AccountFactory
from conpass.tests.factories.client import ClientFactory
from conpass.tests.factories.directory import DirectoryFactory

faker = Faker()


class ContractFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Contract

    name = factory.LazyAttribute(lambda x: faker.name())
    type = factory.LazyAttribute(lambda x: random.choice([t.value for t in Contract.ContractType]))

    account = factory.SubFactory(AccountFactory)
    client = factory.SubFactory(ClientFactory)
    directory = factory.SubFactory(
        DirectoryFactory,
        account=factory.LazyAttribute(lambda x: x.factory_parent.account),
        type=factory.LazyAttribute(lambda x: x.factory_parent.type),
    )
    template = None
    origin = None

    version = ""
    # file = ManyToMany
    is_garbage = False
    is_provider = True
    status = Contract.Status.ENABLE.value

    created_at = factory.LazyAttribute(lambda x: make_aware(faker.date_time()))
    updated_at = factory.LazyAttribute(lambda x: x.created_at)
