import datetime

import pytest
from django.utils.timezone import make_aware

from common.utils import date_utils


@pytest.mark.parametrize('any_day,expected', [
    ["2004-02-15", "2004-02-01"],
    ["2004-12-15", "2004-12-01"],
])
def test__get_first_day_of_month(any_day, expected):
    actual = date_utils.get_first_day_of_month(make_aware(datetime.datetime.strptime(any_day, "%Y-%m-%d")))
    assert actual.strftime('%Y-%m-%d') == expected


@pytest.mark.parametrize('any_day,expected', [
    ["2004-02-15", "2004-02-29"],
    ["2004-12-15", "2004-12-31"],
])
def test__get_last_day_of_month(any_day, expected):
    actual = date_utils.get_last_day_of_month(make_aware(datetime.datetime.strptime(any_day, "%Y-%m-%d")))
    assert actual.strftime('%Y-%m-%d') == expected
