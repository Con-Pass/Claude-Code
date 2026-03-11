from django.template.loader import render_to_string
from sendgrid import Mail

from conpass.mailer.base_mailer import BaseMailer
from conpass.models import User


class ContractUploadMailer(BaseMailer):

    def send_bulk_upload_result_mail(self, user: User, body: str):
        body = render_to_string('mailer/contract/bulk_upload_result_plain.txt', {
            'user': user,
            'body': body,
        })
        mail = Mail(
            from_email=self.default_from_email,
            to_emails=[user.email],
            subject="【ConPass】一括アップロードを受け付けました",
            plain_text_content=body
        )
        self.send(mail, user)

    def send_upload_error_mail(self, user: User, date: str):
        body = render_to_string('mailer/upload/notify_upload_error_plain.txt', {
            'user': user,
            'date': date,
        })
        mail = Mail(
            from_email=self.default_from_email,
            to_emails=[user.email],
            subject="【ConPass】ファイルのアップロードに失敗しました",
            plain_text_content=body
        )
        self.send(mail, user)
