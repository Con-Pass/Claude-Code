import datetime
import random

import factory.django
from django.utils.timezone import make_aware
from faker import Faker

from conpass.models import BPORequest

faker = Faker(locale='ja_JP')


class BPORequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BPORequest

    name = factory.Sequence(lambda n: f"件名{n}")
    body = factory.Sequence(lambda n: f"本文{n}\n二行目\n")
    type = factory.LazyAttribute(lambda x: random.choice([t.value for t in BPORequest.Type]))
    response = BPORequest.Response.BEFORE_START.value
    status = BPORequest.Status.ENABLE.value
    created_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
    updated_at = factory.LazyAttribute(lambda x: make_aware(datetime.datetime.now()))
