import dataclasses
import traceback
from logging import getLogger
from typing import List

import dataclasses_json
import django.db

from conpass.models import Account

logger = getLogger(__name__)


@dataclasses_json.dataclass_json
@dataclasses.dataclass
class Stats:
    succeeded: int = 0
    failed: int = 0
    failed_account_ids: List[int] = dataclasses.field(default_factory=list)


def execute_summarize_every_account(func, **kwargs) -> Stats:
    stats = Stats()
    for account in Account.objects.all():
        try:
            func(account=account, **kwargs)
            stats.succeeded += 1
        except django.db.IntegrityError as e:
            code = e.args[0]
            if code == 1062:
                # Duplicate entry
                logger.warning(f"既にレコードが存在します: {e}", extra={
                    'account': account,
                })
            else:
                logger.error(f"{e} {traceback.format_exc()}")
            stats.failed += 1
            stats.failed_account_ids.append(account.id)
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
            stats.failed += 1
            stats.failed_account_ids.append(account.id)
    return stats
