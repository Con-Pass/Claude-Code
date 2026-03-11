import datetime
from django.template.loader import render_to_string
from sendgrid import Mail

from conpass.mailer.base_mailer import BaseMailer
from conpass.models import User, WorkflowTask


class WorkflowMailer(BaseMailer):

    def send_next_task_request_mail(self, user: User, workflow_task: WorkflowTask):
        client = workflow_task.step.workflow.client
        contract = workflow_task.step.workflow.contract
        task_deadline = workflow_task.step.start_date + datetime.timedelta(days=workflow_task.step.expire_day)
        body = render_to_string('mailer/workflow/task_notification_plain.txt', {
            'user': user,
            'client_name': client.name if client else "",
            'contract_name': contract.name if contract else "",
            'step_name': workflow_task.step.name,
            'task_name': workflow_task.name,
            'task_deadline': task_deadline.strftime('%Y-%m-%d')
        })

        mail = Mail(
            from_email=self.default_from_email,
            to_emails=[user.email],
            subject="【ConPass】ワークフローでタスクが依頼されました",
            plain_text_content=body
        )
        self.send(mail, user)

    def send_notify_task_finish_mail(self, created_by: User, workflow_task: WorkflowTask):
        client = workflow_task.step.workflow.client
        contract = workflow_task.step.workflow.contract
        task_deadline = workflow_task.step.start_date + datetime.timedelta(days=workflow_task.step.expire_day)
        body = render_to_string('mailer/workflow/task_finish_notification_plain.txt', {
            'user': created_by,
            'client_name': client.name if client else "",
            'contract_name': contract.name if contract else "",
            'step_name': workflow_task.step.name,
            'task_name': workflow_task.name,
            'task_deadline': task_deadline.strftime('%Y-%m-%d')
        })

        mail = Mail(
            from_email=self.default_from_email,
            to_emails=[created_by.email],
            subject="【ConPass】ワークフローでタスクが完了しました",
            plain_text_content=body
        )
        self.send(mail, created_by)
