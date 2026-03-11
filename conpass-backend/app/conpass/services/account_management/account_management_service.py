import datetime
import traceback
from logging import getLogger

from django.db.utils import DatabaseError

from conpass.models import Account

logger = getLogger(__name__)


class AccountManagementService:

    def activate_account(self):
        wheres = {
            'status': Account.Status.PREPARE.value,
            'start_date__lte': datetime.date.today(),
        }
        try:
            target = Account.objects.filter(**wheres)
            activated_account = []
            for account in target:
                account.status = Account.Status.ENABLE.value
                account.save()
                activated_account.append(account.id)
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            raise e
        logger.info(f'account activation finished. account_id:{activated_account}')

    def invalidate_account(self):
        wheres = {
            'status': Account.Status.ENABLE.value,
            'cancel_date__lte': datetime.date.today(),
        }
        try:
            target = Account.objects.filter(**wheres)
            invalidated_account = []
            for account in target:
                account.status = Account.Status.SUSPEND.value
                account.save()
                invalidated_account.append(account.id)
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            raise e
        logger.info(f'account invalidation finished. account_id:{invalidated_account}')
