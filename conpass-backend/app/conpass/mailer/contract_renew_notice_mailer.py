from datetime import datetime
from django.template.loader import render_to_string
from sendgrid import Mail
from typing import List
from conpass.models import MetaData, User
from conpass.mailer.base_mailer import BaseMailer


class SendContractRenewNoticeMailer(BaseMailer):
    def send_contract_renew_notice_mail(self, user: User, contract_id: int, metadata_dict: dict):
        corporate_name = ""
        if user.corporate:
            corporate_name = user.corporate.name

        body = render_to_string('mailer/contract/contract_renew_notice.txt', {
            'user_name': user.username,
            'corporate_name': corporate_name,
            'contract_id': contract_id,
            'companya': metadata_dict.get('companya', ''),
            'companyb': metadata_dict.get('companyb', ''),
            'title': metadata_dict.get('title', ''),
            'contractenddate': metadata_dict.get('contractenddate', ''),
            'cancelnotice': metadata_dict.get('cancelnotice', ''),
            'autoupdate': metadata_dict.get('autoupdate', '選択なし'),
        })
        mail = Mail(
            from_email=self.default_from_email,
            to_emails=[user.email],
            subject="【ConPass】契約更新のリマインダー",
            plain_text_content=body
        )
        self.send(mail, user)
