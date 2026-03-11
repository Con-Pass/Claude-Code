from django.conf import settings
from django.template.loader import render_to_string
from sendgrid import Mail

from conpass.mailer.base_mailer import BaseMailer
from conpass.models import User, BPORequest


class BpoMailer(BaseMailer):
    admin_to_address = settings.BPO_MAIL_TO_ADDRESS

    def send_user_request_mail(self, user: User, bpo: BPORequest):
        if bpo.type == bpo.Type.PURCHASE_BOX.value:
            body = render_to_string('mailer/bpo/user_request_plain_add_info_title.txt', {
                'info_title': '■郵送先情報',
                'user': user,
                'bpo': bpo,
            })
        elif bpo.type == bpo.Type.COLLECT.value:
            body = render_to_string('mailer/bpo/user_request_plain_add_info_title.txt', {
                'info_title': '■原本回収情報',
                'user': user,
                'bpo': bpo,
            })
        else:
            body = render_to_string('mailer/bpo/user_request_plain.txt', {
                'user': user,
                'bpo': bpo,
            })
        mail = Mail(
            from_email=self.default_from_email,
            to_emails=[user.email],
            subject="【ConPass】BPO依頼を受け付けました",
            plain_text_content=body
        )
        self.send(mail, user)

    def send_admin_request_mail(self, user: User, bpo: BPORequest):
        if bpo.type == bpo.Type.PURCHASE_BOX.value:
            body = render_to_string('mailer/bpo/admin_request_plain_add_info_title.txt', {
                'info_title': '■郵送先情報',
                'user': user,
                'bpo': bpo,
            })
        elif bpo.type == bpo.Type.COLLECT.value:
            body = render_to_string('mailer/bpo/admin_request_plain_add_info_title.txt', {
                'info_title': '■原本回収情報',
                'user': user,
                'bpo': bpo,
            })
        else:
            body = render_to_string('mailer/bpo/admin_request_plain.txt', {
                'user': user,
                'bpo': bpo,
            })
        mail = Mail(
            from_email=self.default_from_email,
            to_emails=[self.admin_to_address],
            subject="【ConPass】BPO業務依頼通知",
            plain_text_content=body
        )
        self.send(mail, user)
