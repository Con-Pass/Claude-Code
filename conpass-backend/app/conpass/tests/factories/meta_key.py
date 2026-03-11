import datetime

import factory.django
from django.utils.timezone import make_aware

from faker import Faker

from conpass.models import Account, MetaData, MetaKey
from conpass.tests.factories.account import AccountFactory
from conpass.tests.factories.contract import ContractFactory

faker = Faker(locale='ja_JP')


class MetaKeyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MetaKey

    name = factory.Sequence(lambda n: f"key_name_{n}")
    label = factory.Sequence(lambda n: f"key_label_{n}")
    account = factory.SubFactory(AccountFactory)
    type = MetaKey.Type.FREE.value
    is_visible = True
    status = MetaKey.Status.ENABLE.value
    created_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    updated_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
