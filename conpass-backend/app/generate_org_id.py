import os
import random
import string
import django

from django.apps import apps

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conpass.settings')
django.setup()

Account = apps.get_model('conpass', 'account')


def update_org_id_of_account():
    accounts = Account.objects.all()
    for account in accounts:
        account.org_id = create_org_id()
        account.save()


# 半角英数6文字（小文字）
def create_org_id():
    characters = string.ascii_lowercase + string.digits
    unique_string = ''.join(random.choice(characters) for _ in range(6))
    wheres = {'org_id': unique_string}
    is_exist = Account.objects.filter(**wheres).exists()
    if is_exist:
        unique_string = create_org_id()
    return unique_string


# スクリプトの実行
update_org_id_of_account()
