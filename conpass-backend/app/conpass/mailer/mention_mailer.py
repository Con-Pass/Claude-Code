from django.template.loader import render_to_string
from sendgrid import Mail

from conpass.mailer.base_mailer import BaseMailer
from conpass.models import User


class MentionMailer(BaseMailer):

    def send_mention_mail(self, user: User, comment_str, version, contract_url, user_name, contract_name, contract_directry_name, client):
        body = render_to_string('mailer/mention/mention_user_plain.txt', {
            'user': user,
            'comment_str': comment_str,
            'version': version,
            'contract_url': contract_url,
            'user_name': user_name,
            'contract_name': contract_name,
            'contract_directry_name': contract_directry_name,
            'client': client,
        })
        mail = Mail(
            from_email=self.default_from_email,
            to_emails=[user.email],
            subject=f"【ConPass】{user_name}さんがメンションしました。",
            plain_text_content=body
        )
        self.send(mail)
