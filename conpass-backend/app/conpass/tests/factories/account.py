import datetime

import factory.django
from django.utils.timezone import make_aware

from faker import Faker

from conpass.models import Account

faker = Faker(locale='ja_JP')


class AccountFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Account

    name = factory.LazyAttribute(lambda x: faker.company())
    created_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    updated_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
