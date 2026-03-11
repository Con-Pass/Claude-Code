# GCP本番環境
import os  # noqa

from config.settings import *

DEBUG = False

REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [  # noqa: F405
    'rest_framework.renderers.JSONRenderer',
    # 'rest_framework.renderers.BrowsableAPIRenderer',
]

# メール宛先
BPO_MAIL_TO_ADDRESS = os.environ.get('BPO_MAIL_TO_ADDRESS', default='ozawa@ultinet.co.jp')
SUPPORT_MAIL_TO_ADDRESS = os.environ.get('SUPPORT_MAIL_TO_ADDRESS', default='ozawa@ultinet.co.jp')
