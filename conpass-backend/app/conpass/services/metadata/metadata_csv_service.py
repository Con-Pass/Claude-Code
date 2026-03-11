import dataclasses
from typing import List, Optional
from logging import getLogger

from django.db import connection

from conpass.models import Account

logger = getLogger(__name__)


@dataclasses.dataclass
class MetadataCsvItem:
    contract_id: int
    metakey_id: int
    metadata_id: Optional[int]
    contract_name: str
    metakey_name: str
    metadata_value: Optional[str]
    metadate_date_value: Optional[str]


class MetadataCsvService:
    def get_metadata_csv_generator(self, account: Account, meta_key_ids: List[int]):
        where_in_placeholder = "({})".format(", ".join(['%s'] * len(meta_key_ids)))
        query = f"""SELECT conpass_contract.id as contract_id,
                          conpass_metakey.id as metakey_id,
                          conpass_metadata.id as metadata_id,
                          conpass_contract.name as contract_name,
                          conpass_metakey.name as metakey_name,
                          conpass_metadata.value as metadata_value,
                          conpass_metadata.date_value as metadata_date_value
                   FROM conpass_contract
                            LEFT JOIN conpass_metakey
                                      ON (conpass_metakey.account_id IS NULL OR conpass_metakey.account_id = %s)
                            LEFT JOIN conpass_metadata
                                      ON conpass_contract.id = conpass_metadata.contract_id
                                          AND conpass_metakey.id = conpass_metadata.key_id
                                          AND conpass_metadata.status = 1
                   WHERE conpass_contract.account_id = %s
                     AND conpass_metakey.status = 1
                     AND conpass_contract.status <> 0
                     AND (conpass_metakey.type = 2 OR (conpass_metakey.type = 1 and conpass_metadata.id is not NULL))
                     AND conpass_metakey.id in {where_in_placeholder}
                   ORDER BY conpass_contract.id, conpass_metakey.id
"""
        logger.info(query)

        with connection.cursor() as cursor:
            cursor.execute(query, (account.id, account.id, *meta_key_ids))
            for data in cursor.fetchall():
                yield MetadataCsvItem(*data)
