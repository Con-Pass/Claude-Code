from rest_framework import serializers

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


# --- PlaybookTemplate ---

class PlaybookTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaybookTemplate
        fields = ['id', 'name', 'industry', 'description', 'default_clause_policies',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


# --- TenantPlaybook ---

class TenantPlaybookListSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True, default=None)

    class Meta:
        model = TenantPlaybook
        fields = ['id', 'name', 'template', 'template_name', 'your_side',
                  'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class TenantPlaybookCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantPlaybook
        fields = ['name', 'template', 'your_side']


class TenantPlaybookUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantPlaybook
        fields = ['name', 'template', 'your_side', 'is_active']


class ApplyTemplateSerializer(serializers.Serializer):
    template_id = serializers.IntegerField()


# --- ClausePolicy ---

class ClausePolicySerializer(serializers.ModelSerializer):
    clause_type_display = serializers.CharField(source='get_clause_type_display', read_only=True)

    class Meta:
        model = ClausePolicy
        fields = ['id', 'clause_type', 'clause_type_display', 'standard_position',
                  'acceptable_range', 'escalation_triggers', 'context_rules',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ClausePolicyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClausePolicy
        fields = ['clause_type', 'standard_position', 'acceptable_range',
                  'escalation_triggers', 'context_rules']


class ClausePolicyUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClausePolicy
        fields = ['standard_position', 'acceptable_range',
                  'escalation_triggers', 'context_rules']


# --- TenantRuleSet / TenantRule ---

class TenantRuleSerializer(serializers.ModelSerializer):
    rule_type_display = serializers.CharField(source='get_rule_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)

    class Meta:
        model = TenantRule
        fields = ['id', 'rule_set', 'rule_type', 'rule_type_display', 'name',
                  'condition', 'action', 'severity', 'severity_display',
                  'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class TenantRuleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantRule
        fields = ['rule_set', 'rule_type', 'name', 'condition', 'action', 'severity']


class TenantRuleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantRule
        fields = ['rule_type', 'name', 'condition', 'action', 'severity', 'is_active']


# --- RuleEvaluationLog ---

class RuleEvaluationLogSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source='rule.name', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    severity = serializers.CharField(source='rule.severity', read_only=True)

    class Meta:
        model = RuleEvaluationLog
        fields = ['id', 'rule', 'rule_name', 'contract', 'evaluated_at',
                  'result', 'result_display', 'severity', 'detail']
        read_only_fields = ['id', 'evaluated_at']


# --- ResponseTemplate / TemplateVariable ---

class TemplateVariableSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateVariable
        fields = ['id', 'variable_name', 'description', 'is_required']
        read_only_fields = ['id']


class ResponseTemplateSerializer(serializers.ModelSerializer):
    variables = TemplateVariableSerializer(many=True, read_only=True)
    inquiry_type_display = serializers.CharField(source='get_inquiry_type_display', read_only=True)

    class Meta:
        model = ResponseTemplate
        fields = ['id', 'inquiry_type', 'inquiry_type_display', 'name',
                  'subject_template', 'body_template', 'escalation_triggers',
                  'is_active', 'variables', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ResponseTemplateCreateSerializer(serializers.ModelSerializer):
    variables = TemplateVariableSerializer(many=True, required=False)

    class Meta:
        model = ResponseTemplate
        fields = ['inquiry_type', 'name', 'subject_template', 'body_template',
                  'escalation_triggers', 'variables']


class ResponseTemplateUpdateSerializer(serializers.ModelSerializer):
    variables = TemplateVariableSerializer(many=True, required=False)

    class Meta:
        model = ResponseTemplate
        fields = ['inquiry_type', 'name', 'subject_template', 'body_template',
                  'escalation_triggers', 'is_active', 'variables']
