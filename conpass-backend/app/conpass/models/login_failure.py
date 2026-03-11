from django.utils import timezone
from datetime import timedelta
from django.db import models


class LoginFailure(models.Model):
    LOCK_TIME = 5
    LOCK_ATTEMPTS_COUNT = 5
    FLL_LOCK_ATTEMPTS_COUNT = 3

    email = models.EmailField()
    count = models.IntegerField(default=0)
    lock_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def check_lock_status(cls, login_failure):
        if not login_failure:
            return False, ""
        since_last_failure = timezone.now() - login_failure.updated_at
        # フルロック
        if login_failure.lock_count >= cls.FLL_LOCK_ATTEMPTS_COUNT:
            return True, "アカウントが完全にロックされました。パスワードを変更してください。"
        elif login_failure.count >= cls.LOCK_ATTEMPTS_COUNT and since_last_failure < timedelta(minutes=cls.LOCK_TIME):
            return True, "一時的にロックされています。5分後に再試行してください。"
        else:
            return False, ""
