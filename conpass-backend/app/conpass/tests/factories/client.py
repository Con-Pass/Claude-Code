import datetime

import factory.django
from django.utils.timezone import make_aware
from faker import Faker

from conpass.models import Client
from conpass.tests.factories.account import AccountFactory
from conpass.tests.factories.corporate import CorporateFactory

faker = Faker(locale='ja_JP')


class ClientFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Client

    name = factory.LazyAttribute(lambda x: faker.company())
    provider_account = factory.SubFactory(AccountFactory)
    corporate = factory.SubFactory(CorporateFactory)
    status = Client.Status.ENABLE.value
    created_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    updated_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
