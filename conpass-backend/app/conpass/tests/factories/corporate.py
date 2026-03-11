import datetime

import factory.django
from django.utils.timezone import make_aware
from faker import Faker

from conpass.models import Corporate
from conpass.tests.factories.account import AccountFactory

faker = Faker(locale='ja_JP')


class CorporateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Corporate

    name = factory.LazyAttribute(lambda x: faker.company())
    address = factory.LazyAttribute(lambda x: faker.address())
    executive_name = factory.LazyAttribute(lambda x: faker.name())
    sales_name = factory.LazyAttribute(lambda x: faker.name())
    service = factory.LazyAttribute(lambda x: faker.safe_color_name())
    url = factory.LazyAttribute(lambda x: faker.url())
    tel = factory.LazyAttribute(lambda x: faker.phone_number())
    status = Corporate.Status.ENABLE.value
    created_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    updated_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))

    account = factory.SubFactory(AccountFactory)
