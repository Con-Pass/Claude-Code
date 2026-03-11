from django.template.loader import render_to_string
from sendgrid import Mail

from conpass.mailer.base_mailer import BaseMailer
from conpass.models import User


class ComplianceAlertMailer(BaseMailer):
    """コンプライアンスアラートメール送信"""

    def send_compliance_alert_mail(
        self,
        user: User,
        rule_name: str,
        rule_severity: str,
        contract_id: int,
        contract_name: str,
        result: str,
        detail: str,
        recommended_action: str,
    ):
        """個別コンプライアンスアラートメールを送信する"""
        corporate_name = ""
        if user.corporate:
            corporate_name = user.corporate.name

        severity_display = {
            'INFO': '情報',
            'WARNING': '警告',
            'CRITICAL': '緊急',
        }.get(rule_severity, rule_severity)

        result_display = {
            'WARN': '警告',
            'FAIL': '失敗',
        }.get(result, result)

        body = render_to_string('mailer/compliance/compliance_alert_plain.txt', {
            'user_name': user.username,
            'corporate_name': corporate_name,
            'rule_name': rule_name,
            'severity': severity_display,
            'contract_id': contract_id,
            'contract_name': contract_name,
            'result': result_display,
            'detail': detail,
            'recommended_action': recommended_action,
        })

        subject_prefix = ""
        if rule_severity == 'CRITICAL':
            subject_prefix = "[緊急] "

        mail = Mail(
            from_email=self.default_from_email,
            to_emails=[user.email],
            subject=f"【ConPass】{subject_prefix}コンプライアンスアラート: {rule_name}",
            plain_text_content=body,
        )
        self.send(mail, user)

    def send_daily_summary_mail(
        self,
        user: User,
        total_warn_count: int,
        total_fail_count: int,
        critical_items: list,
        summary_date: str,
    ):
        """日次コンプライアンスサマリーメールを送信する"""
        corporate_name = ""
        if user.corporate:
            corporate_name = user.corporate.name

        body = render_to_string('mailer/compliance/compliance_daily_summary_plain.txt', {
            'user_name': user.username,
            'corporate_name': corporate_name,
            'summary_date': summary_date,
            'total_warn_count': total_warn_count,
            'total_fail_count': total_fail_count,
            'critical_items': critical_items,
        })

        mail = Mail(
            from_email=self.default_from_email,
            to_emails=[user.email],
            subject=f"【ConPass】コンプライアンス日次サマリー ({summary_date})",
            plain_text_content=body,
        )
        self.send(mail, user)
