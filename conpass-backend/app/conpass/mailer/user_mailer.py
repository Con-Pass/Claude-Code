from django.template.loader import render_to_string
from sendgrid import Mail

from conpass.mailer.base_mailer import BaseMailer
from conpass.models import User


class UserMailer(BaseMailer):

    def send_user_create_mail(self, user: User):
        body = render_to_string('mailer/user/user_create_plain.txt', {
            'user': user,
        })
        mail = Mail(
            from_email=self.default_from_email,
            to_emails=[user.email],
            subject="【ConPass】ConPassユーザー情報が追加されました。",
            plain_text_content=body
        )
        self.send(mail, user)

    def send_user_modify_mail(self, user: User, login_user: User):
        body = render_to_string('mailer/user/user_modify_plain.txt', {
            'user': user,
            'login_user': login_user,
        })
        mail = Mail(
            from_email=self.default_from_email,
            to_emails=[user.email],
            subject="【ConPass】ConPassユーザー情報が修正されました。",
            plain_text_content=body,
            is_multiple=True
        )
        self.send(mail, user)
