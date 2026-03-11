import os
import django
import datetime
import traceback
from django.utils.timezone import make_aware
from django.db import DatabaseError
from logging import getLogger

from django.apps import apps

from conpass.services.contract.contract_service import ContractService

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conpass.settings')
django.setup()


ContractBody = apps.get_model('conpass', 'contractbody')
Contract = apps.get_model('conpass', 'contract')
logger = getLogger(__name__)


def versioning_contract_body():
    contract_ids = ContractBody.objects.values('contract_id').distinct()
    contract_service = ContractService()
    now = make_aware(datetime.datetime.now())

    for contract_id in contract_ids:
        contract = Contract.objects.get(pk=contract_id['contract_id'])
        contractbodys = ContractBody.objects.filter(contract_id=contract_id['contract_id']).order_by('updated_at')
        maijor_version = 1
        minor_version = 0
        for i, contractbody in enumerate(contractbodys):
            if i == len(contractbodys) - 1:
                contractbody.is_adopted = contract.type == 2
            contractbody.version = str(maijor_version) + "." + str(minor_version)
            contractbody.save()
            minor_version += 1

            # 全検索用モデルとMeilisearchに保存
            try:
                contract_service.save_contract_body_search_task(contractbody, now)
            except Exception as e:
                logger.error(f"contract_body_search error:{e}")


# スクリプトの実行
versioning_contract_body()
