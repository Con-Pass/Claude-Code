import datetime
import random
import factory
from django.utils.timezone import make_aware
from faker import Faker

from conpass.models import File
from conpass.tests.factories.account import AccountFactory

faker = Faker()


class FileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = File

    account = factory.SubFactory(AccountFactory)
    name = factory.LazyAttribute(lambda x: faker.file_name())
    type = factory.LazyAttribute(lambda x: random.choice([t.value for t in File.Type]))
    description = factory.LazyAttribute(lambda x: faker.text())
    url = factory.LazyAttribute(lambda x: faker.url())
    size = factory.LazyAttribute(lambda x: random.randint(1, 10_000_000))
    status = File.Status.ENABLE.value
    created_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    updated_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
