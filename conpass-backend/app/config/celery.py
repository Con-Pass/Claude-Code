import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
from celery.signals import setup_logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')

app = Celery('config')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')


@setup_logging.connect
def config_loggers(*args, **kwargs):
    from logging.config import dictConfig
    from django.conf import settings
    dictConfig(settings.LOGGING)


# Load task modules from all registered Django apps.
app.autodiscover_tasks([
    'conpass',
    'conpass.services.account_storage_summary',
    'conpass.services.account_active_summary',
    'conpass.services.contract',
])


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
