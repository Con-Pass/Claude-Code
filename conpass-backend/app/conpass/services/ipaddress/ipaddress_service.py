import traceback
from datetime import datetime

from django.db import DatabaseError
from django.utils.timezone import make_aware

from conpass.models import User, IpAddress
from logging import getLogger
from conpass.models.constants import Statusable

logger = getLogger(__name__)


class IpAddressService:

    def delete_ip_address_data(self, delete_ip_addresses: IpAddress, login_user: User):
        now = make_aware(datetime.now())
        try:
            for delete_ip_address in delete_ip_addresses:
                delete_ip_address.status = Statusable.Status.DISABLE.value
                delete_ip_address.updated_by = login_user
                delete_ip_address.updated_at = now
            IpAddress.objects.bulk_update(delete_ip_addresses, fields=['status', 'updated_by', 'updated_at'])
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            raise e
