import datetime
import random

import factory.django
from django.utils.timezone import make_aware
from faker import Faker

from conpass.models import Directory
from conpass.tests.factories.account import AccountFactory

faker = Faker(locale='ja_JP')


class DirectoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Directory

    name = factory.Sequence(lambda n: f'ディレクトリ{n}')
    level = 0
    parent = None
    type = factory.LazyAttribute(lambda x: random.choice([t.value for t in Directory.ContractType]))
    memo = factory.LazyAttribute(lambda x: faker.text())
    status = Directory.Status.ENABLE.value
    created_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    updated_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))

    account = factory.SubFactory(AccountFactory)
