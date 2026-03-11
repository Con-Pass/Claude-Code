import datetime
import calendar


def get_first_day_of_month(any_day: datetime.date) -> datetime.date:
    return any_day.replace(day=1)


def get_last_day_of_month(any_day: datetime.date) -> datetime.date:
    _weekday, days = calendar.monthrange(any_day.year, any_day.month)
    return any_day.replace(day=days)
