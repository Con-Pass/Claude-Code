import datetime
import random

import factory.django
from django.utils.timezone import make_aware
from faker import Faker

from common.utils import date_utils
from conpass.models import AccountStorageSummary
from conpass.tests.factories.account import AccountFactory

faker = Faker(locale='ja_JP')


class AccountStorageSummaryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AccountStorageSummary

    account = factory.SubFactory(AccountFactory)
    file_size_total = factory.LazyAttribute(lambda x: random.randint(1_000, 100_000_000_000))
    file_num = factory.LazyAttribute(lambda x: random.randint(1, 100))
    cycle = AccountStorageSummary.Cycle.DAILY.value
    date_from = factory.LazyAttribute(lambda x: faker.date())
    date_to = factory.LazyAttribute(lambda x: AccountStorageSummaryFactory._date_to(x))
    created_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    updated_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))

    @classmethod
    def _date_to(cls, x):
        if x.cycle == AccountStorageSummary.Cycle.DAILY.value:
            return x.date_from
        elif x.cycle == AccountStorageSummary.Cycle.MONTHLY.value:
            return date_utils.get_last_day_of_month(x.date_from)
        else:
            assert False, f"Invalid cycle: {x.cycle}"
