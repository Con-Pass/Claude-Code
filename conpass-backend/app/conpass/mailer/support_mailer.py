from django.conf import settings
from django.template.loader import render_to_string
from sendgrid import Mail

from conpass.mailer.base_mailer import BaseMailer
from conpass.models import User, Support


class SupportMailer(BaseMailer):
    admin_to_address = settings.SUPPORT_MAIL_TO_ADDRESS

    def send_user_request_mail(self, user: User, support: Support):
        body = render_to_string('mailer/support/user_request_plain.txt', {
            'user': user,
            'support': support,
        })
        mail = Mail(
            from_email=self.default_from_email,
            to_emails=[user.email],
            subject="【ConPass】お問い合わせを受け付けました",
            plain_text_content=body
        )
        self.send(mail, user)

    def send_admin_request_mail(self, user: User, support: Support):
        body = render_to_string('mailer/support/admin_request_plain.txt', {
            'user': user,
            'support': support,
        })
        mail = Mail(
            from_email=self.default_from_email,
            to_emails=[self.admin_to_address],
            subject="【ConPass】お問い合わせ",
            plain_text_content=body
        )
        self.send(mail, user)
