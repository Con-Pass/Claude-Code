import datetime
import random

import factory.django
from django.utils.timezone import make_aware
from faker import Faker

from conpass.models import Support

faker = Faker(locale='ja_JP')


class SupportFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Support

    name = factory.Sequence(lambda n: f"件名{n}")
    body = factory.Sequence(lambda n: f"本文{n}\n二行目\n")
    type = factory.LazyAttribute(lambda x: random.choice([t.value for t in Support.Type]))
    response = Support.Response.BEFORE_START.value
    status = Support.Status.ENABLE.value
    created_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    updated_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
