from django.conf import settings
from django.utils import timezone
from conpass.services.sendgrid.sendgrid_service import SendGrid
from sendgrid.helpers.mail import Mail
from conpass.models import User, Account


class BaseMailer:
    default_from_email = settings.SENDGRID_DEFAULT_FROM_ADDRESS

    def __init__(self):
        self._send_grid = SendGrid()

    def send(self, mail: Mail, user: User = None):
        """
        to_emails に複数アドレスを指定する場合、mail で以下パラメータを設定すると、個別にメールが飛ぶようになります（BCCのような形）
        設定していない場合、to に全員分のメールアドレスが入ったメールになってしまうので、ご注意ください
        is_multiple=True
        メール送信成功時は response.status_code=202 が返ります
        """
        # 無効のアカウントの場合メールは送らない
        if user and user.account:
            stop_account_status = [Account.Status.DISABLE.value, Account.Status.SUSPEND.value]
            status = user.account.status
            cancel_date = user.account.cancel_date
            if status in stop_account_status or (cancel_date and cancel_date <= timezone.now().date()):
                return

        self._send_grid.send(mail)
