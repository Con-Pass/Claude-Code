import os
import django
import pyotp

from django.apps import apps

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conpass.settings')
django.setup()


YourModel = apps.get_model('conpass', 'user')


def update_otp_secrets():
    objects = YourModel.objects.all()
    for obj in objects:
        obj.otp_secret = pyotp.random_base32()
        obj.save()


# スクリプトの実行
update_otp_secrets()
