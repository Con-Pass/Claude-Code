import datetime

import factory.django
from django.contrib.auth.hashers import make_password
from django.utils.timezone import make_aware
from faker import Faker

from conpass.models import User
from conpass.tests.factories.account import AccountFactory
from conpass.tests.factories.client import ClientFactory
from conpass.tests.factories.corporate import CorporateFactory

faker = Faker(locale='ja_JP')


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    login_name = factory.LazyAttribute(lambda x: faker.ascii_safe_email())
    username = factory.LazyAttribute(lambda x: faker.name())
    email = factory.LazyAttribute(lambda x: x.login_name)
    type = User.Type.ACCOUNT.value
    account = factory.SubFactory(AccountFactory)
    client = factory.SubFactory(ClientFactory)
    corporate = factory.SubFactory(CorporateFactory)
    tel = factory.LazyAttribute(lambda x: faker.phone_number())
    memo = factory.LazyAttribute(lambda x: faker.text())
    status = User.Status.ENABLE.value
    password = "password"
    created_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    updated_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override the default ``_create`` with our custom call."""
        kwargs['password'] = make_password(kwargs['password'])
        return super(UserFactory, cls)._create(model_class, *args, **kwargs)
