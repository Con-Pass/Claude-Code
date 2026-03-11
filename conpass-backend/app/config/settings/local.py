import os

from config.settings import *
from config.settings import REST_FRAMEWORK, LOGGING, BASE_DIR

DEBUG = True

REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [
    'rest_framework.renderers.JSONRenderer',
    'rest_framework.renderers.BrowsableAPIRenderer',
]

# ローカルでは基本simpleフォーマットでファイル出力
LOGS_DIR = os.path.join(BASE_DIR, '../logs')
LOGGING.update({
    'handlers': {
        'console-simple': {
            'filters': [],
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file-json': {
            'filters': [],
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'django-json.log'),
            'when': 'D',
            'interval': 1,
            'formatter': 'json',
        },
        'file-simple': {
            'filters': [],
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'django.log'),
            'when': 'D',
            'interval': 1,
            'formatter': 'simple',
        },
        'db-simple': {
            'filters': [],
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, '../logs/db.log'),
            'when': 'D',
            'interval': 1,
            'formatter': 'simple',
        },
        'celery-simple': {
            'filters': [],
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'celery.log'),
            'when': 'D',
            'interval': 1,
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django.request': {
            'level': 'INFO',
        },
        'django.db.backends': {
            'handlers': ['db-simple'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'celery': {
            'handlers': ['celery-simple', 'console-simple'],
            'level': 'DEBUG',
            'propagate': False,
        }
    },
    'root': {
        'handlers': [
            'console-simple',
            'file-simple',
            'file-json',
        ],
        'level': os.environ.get('LOG_LEVEL', 'INFO')
    }
})
