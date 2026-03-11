import datetime

import factory.django
from django.utils.timezone import make_aware

from faker import Faker

from conpass.models import Account, MetaData
from conpass.tests.factories.contract import ContractFactory
from conpass.tests.factories.meta_key import MetaKeyFactory

faker = Faker(locale='ja_JP')


class MetaDataFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MetaData

    contract = factory.SubFactory(ContractFactory)
    key = factory.SubFactory(MetaKeyFactory)
    check = False
    value = factory.Sequence(lambda n: f'メタデータ_{n}')
    date_value = factory.LazyAttribute(lambda x: make_aware(faker.date_time()))
    score = 0.0
    start_offset = 0
    end_offset = 0
    status = MetaData.Status.ENABLE.value
    lock = False
    created_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    updated_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
