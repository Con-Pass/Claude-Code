import datetime
import random

import factory.django
from django.utils.timezone import make_aware
from faker import Faker

from common.utils import date_utils
from conpass.models import AccountActiveSummary
from conpass.tests.factories.account import AccountFactory

faker = Faker(locale='ja_JP')


class AccountActiveSummaryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AccountActiveSummary

    account = factory.SubFactory(AccountFactory)
    active_contracts_count = factory.LazyAttribute(lambda x: random.randint(10, 1000))
    cycle = AccountActiveSummary.Cycle.DAILY.value
    date_from = factory.LazyAttribute(lambda x: faker.date())
    date_to = factory.LazyAttribute(lambda x: AccountActiveSummaryFactory._date_to(x))
    created_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    updated_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))

    @classmethod
    def _date_to(cls, x):
        if x.cycle == AccountActiveSummary.Cycle.DAILY.value:
            return x.date_from
        elif x.cycle == AccountActiveSummary.Cycle.MONTHLY.value:
            return date_utils.get_last_day_of_month(x.date_from)
        else:
            assert False, f"Invalid cycle: {x.cycle}"
