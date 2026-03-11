from datetime import datetime, timedelta
from django.template.loader import render_to_string
from sendgrid import Mail

from conpass.mailer.base_mailer import BaseMailer
from conpass.models import User


class MfaMailer(BaseMailer):

    def send_otp_mail(self, user: User, otp: str,):

        totp_limit = ""
        now = datetime.now().strftime("%H:%M").split(":")
        if now[1].endswith(("0", "1", "2", "3", "4")):
            totp_limit = now[0] + "時" + now[1][-2] + "4" + "分(Asia/Tokyo)"
        if now[1].endswith(("5", "6", "7", "8", "9")):
            totp_limit = now[0] + "時" + now[1][-2] + "9" + "分(Asia/Tokyo)"

        body = render_to_string('mailer/mfa/send_otp_plain.txt', {
            'user': user,
            'otp': otp,
            'otp_limit': totp_limit,
        })

        mail = Mail(
            from_email=self.default_from_email,
            to_emails=[user.email],
            subject="【ConPass】ワンタイムパスワードが発行されました",
            plain_text_content=body
        )
        self.send(mail, user)
