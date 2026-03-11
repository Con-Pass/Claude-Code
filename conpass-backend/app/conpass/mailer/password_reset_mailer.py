from datetime import datetime
from django.template.loader import render_to_string
from sendgrid import Mail

from conpass.mailer.base_mailer import BaseMailer
from conpass.models import User


class PasswordRestMailer(BaseMailer):
    def send_password_reset_mail(self, user: User, new_password: str):
        body = render_to_string('mailer/user/user_password_reset.txt', {
            'user': user,
            'new_password': new_password,
            'formatted_now': datetime.now().strftime("%Y年%m月%d日%H時%M分")
        })
        mail = Mail(
            from_email=self.default_from_email,
            to_emails=[user.email],
            subject="【ConPass】パスワードリセットのご案内",
            plain_text_content=body
        )
        self.send(mail, user)
