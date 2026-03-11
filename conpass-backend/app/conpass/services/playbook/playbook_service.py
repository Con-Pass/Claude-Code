from logging import getLogger

from conpass.models.playbook import (
    PlaybookTemplate,
    TenantPlaybook,
    ClausePolicy,
    TenantRuleSet,
    TenantRule,
    RuleEvaluationLog,
    ResponseTemplate,
    TemplateVariable,
)

logger = getLogger(__name__)


class PlaybookService:

    @staticmethod
    def apply_template(playbook: TenantPlaybook, template: PlaybookTemplate):
        """
        テンプレートのdefault_clause_policiesからClausePolicyを一括生成する。
        既存のClausePolicyがある場合は上書きせずスキップする。
        """
        policies = template.default_clause_policies
        if not isinstance(policies, dict):
            return []

        created = []
        for clause_type, policy_data in policies.items():
            if not isinstance(policy_data, dict):
                continue
            obj, was_created = ClausePolicy.objects.get_or_create(
                playbook=playbook,
                clause_type=clause_type,
                defaults={
                    'standard_position': policy_data.get('standard_position', {}),
                    'acceptable_range': policy_data.get('acceptable_range', {}),
                    'escalation_triggers': policy_data.get('escalation_triggers', {}),
                    'context_rules': policy_data.get('context_rules', {}),
                }
            )
            if was_created:
                created.append(obj)

        # テンプレートをplaybookに紐付け
        playbook.template = template
        playbook.save(update_fields=['template', 'updated_at'])

        return created

    @staticmethod
    def create_response_template_with_variables(account, data):
        """
        ResponseTemplateとTemplateVariableを同時に作成する。
        """
        variables_data = data.pop('variables', [])
        template = ResponseTemplate.objects.create(account=account, **data)
        for var_data in variables_data:
            TemplateVariable.objects.create(template=template, **var_data)
        return template

    @staticmethod
    def update_response_template_with_variables(template, data):
        """
        ResponseTemplateとTemplateVariableを同時に更新する。
        variablesが指定された場合は全件入れ替え。
        """
        variables_data = data.pop('variables', None)

        for key, value in data.items():
            setattr(template, key, value)
        template.save()

        if variables_data is not None:
            template.variables.all().delete()
            for var_data in variables_data:
                TemplateVariable.objects.create(template=template, **var_data)

        return template
