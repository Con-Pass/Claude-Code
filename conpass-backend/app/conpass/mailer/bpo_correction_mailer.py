from django.conf import settings
from django.template.loader import render_to_string
from sendgrid import Mail

from conpass.mailer.base_mailer import BaseMailer
from conpass.models import User


class BpoCorrectionMailer(BaseMailer):
    admin_to_address = settings.BPO_MAIL_TO_ADDRESS

    def send_user_request_mail(self, user: User, type_display: str, subject: str, body: str):
        body = render_to_string('mailer/bpo_correction/user_request_plain.txt', {
            'user': user,
            'type_display': type_display,
            'subject': subject,
            'body': body,
        })
        mail = Mail(
            from_email=self.default_from_email,
            to_emails=[user.email],
            subject="【ConPass】BPO依頼を受け付けました",
            plain_text_content=body
        )
        self.send(mail, user)

    def send_admin_request_mail(self, user: User, type_display: str, subject: str, body: str):
        body = render_to_string('mailer/bpo_correction/admin_request_plain.txt', {
            'user': user,
            'type_display': type_display,
            'body': body,
        })
        mail = Mail(
            from_email=self.default_from_email,
            to_emails=[self.admin_to_address],
            subject=subject,
            plain_text_content=body
        )
        self.send(mail, user)
