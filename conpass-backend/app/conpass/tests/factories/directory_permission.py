import datetime

import factory.django
from django.utils.timezone import make_aware
from faker import Faker

from conpass.models import DirectoryPermission
from conpass.tests.factories.directory import DirectoryFactory
from conpass.tests.factories.user import UserFactory

faker = Faker(locale='ja_JP')


class DirectoryPermissionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DirectoryPermission

    directory = factory.SubFactory(DirectoryFactory)
    user = factory.SubFactory(UserFactory)
    group = None
    is_visible = True
    status = DirectoryPermission.Status.ENABLE.value
    created_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    updated_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
