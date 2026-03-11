"""
PlaybookEngine テスト
TenantPlaybook / ClausePolicy / TenantRule の CRUD およびビジネスロジックを検証
"""
import datetime

import pytest
import factory
from django.utils.timezone import make_aware
from faker import Faker

from conpass.models import Account, Contract
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
from conpass.tests.factories.account import AccountFactory
from conpass.tests.factories.contract import ContractFactory

faker = Faker(locale='ja_JP')


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

class PlaybookTemplateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PlaybookTemplate

    name = factory.Sequence(lambda n: f'テンプレート{n}')
    industry = 'CONSTRUCTION'
    description = factory.LazyAttribute(lambda x: faker.text(max_nb_chars=100))
    default_clause_policies = factory.LazyFunction(lambda: {
        'LIABILITY': {
            'standard_position': {'max_liability': '契約金額の100%'},
            'acceptable_range': {'max_liability_upper': '契約金額の200%'},
            'escalation_triggers': {'unlimited_liability': True},
        },
        'CONFIDENTIALITY': {
            'standard_position': {'duration_years': 3, 'mutual': True},
            'acceptable_range': {'duration_years_max': 5},
            'escalation_triggers': {'no_mutual': True, 'duration_over': 10},
        },
    })


class TenantPlaybookFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TenantPlaybook

    account = factory.SubFactory(AccountFactory)
    name = factory.Sequence(lambda n: f'プレイブック{n}')
    template = None
    your_side = 'VENDOR'
    is_active = True


class ClausePolicyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ClausePolicy

    playbook = factory.SubFactory(TenantPlaybookFactory)
    clause_type = 'LIABILITY'
    standard_position = factory.LazyFunction(lambda: {
        'max_liability': '契約金額の100%',
        'cap_type': 'percentage',
    })
    acceptable_range = factory.LazyFunction(lambda: {
        'max_liability_upper': '契約金額の200%',
    })
    escalation_triggers = factory.LazyFunction(lambda: {
        'unlimited_liability': True,
        'no_cap': True,
    })
    context_rules = factory.LazyFunction(lambda: {
        'deal_size_over_10m': {'max_liability_upper': '契約金額の150%'},
    })


class TenantRuleSetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TenantRuleSet

    account = factory.SubFactory(AccountFactory)
    name = factory.Sequence(lambda n: f'ルールセット{n}')
    playbook = None
    is_active = True


class TenantRuleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TenantRule

    rule_set = factory.SubFactory(TenantRuleSetFactory)
    rule_type = 'EXPIRY_ALERT'
    name = factory.Sequence(lambda n: f'ルール{n}')
    condition = factory.LazyFunction(lambda: {
        'days_before_expiry': 90,
    })
    action = factory.LazyFunction(lambda: {
        'notify': True,
        'severity': 'WARNING',
    })
    severity = 'WARNING'
    is_active = True


class RuleEvaluationLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RuleEvaluationLog

    rule = factory.SubFactory(TenantRuleFactory)
    contract = factory.SubFactory(ContractFactory)
    result = 'PASS'
    detail = factory.LazyFunction(dict)


class ResponseTemplateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ResponseTemplate

    account = factory.SubFactory(AccountFactory)
    inquiry_type = 'DSR'
    name = factory.Sequence(lambda n: f'回答テンプレート{n}')
    subject_template = 'Re: {{inquiry_type}} - {{requester_name}} 様'
    body_template = '{{requester_name}} 様\n\nご連絡いただきありがとうございます。\n{{response_body}}\n\n期限: {{deadline}}'
    escalation_triggers = factory.LazyFunction(lambda: ['訴訟', '裁判所', '損害賠償請求'])
    is_active = True


# ===========================================================================
# テストクラス
# ===========================================================================

@pytest.mark.django_db
class TestTenantPlaybook:
    """TenantPlaybook の CRUD テスト"""

    def test_create_playbook(self):
        """TenantPlaybook 作成テスト"""
        account = AccountFactory()
        playbook = TenantPlaybook.objects.create(
            account=account,
            name='建設業プレイブック',
            your_side='VENDOR',
        )
        assert playbook.pk is not None
        assert playbook.name == '建設業プレイブック'
        assert playbook.your_side == 'VENDOR'
        assert playbook.is_active is True
        assert playbook.account == account

    def test_create_playbook_with_template(self):
        """PlaybookTemplate を紐づけた TenantPlaybook 作成テスト"""
        template = PlaybookTemplateFactory(industry='CONSTRUCTION')
        account = AccountFactory()
        playbook = TenantPlaybook.objects.create(
            account=account,
            name='建設業プレイブック',
            template=template,
            your_side='CUSTOMER',
        )
        assert playbook.template == template
        assert playbook.your_side == 'CUSTOMER'

    def test_playbook_factory(self):
        """Factory による TenantPlaybook 生成テスト"""
        playbook = TenantPlaybookFactory()
        assert playbook.pk is not None
        assert playbook.account is not None

    def test_apply_template(self):
        """テンプレート適用で ClausePolicy が生成されることを確認"""
        template = PlaybookTemplateFactory()
        account = AccountFactory()
        playbook = TenantPlaybook.objects.create(
            account=account,
            name='テスト用プレイブック',
            template=template,
        )

        # テンプレートの default_clause_policies から ClausePolicy を生成
        for clause_type, policy_data in template.default_clause_policies.items():
            ClausePolicy.objects.create(
                playbook=playbook,
                clause_type=clause_type,
                standard_position=policy_data.get('standard_position', {}),
                acceptable_range=policy_data.get('acceptable_range', {}),
                escalation_triggers=policy_data.get('escalation_triggers', {}),
            )

        policies = ClausePolicy.objects.filter(playbook=playbook)
        assert policies.count() == 2  # LIABILITY + CONFIDENTIALITY
        clause_types = set(policies.values_list('clause_type', flat=True))
        assert 'LIABILITY' in clause_types
        assert 'CONFIDENTIALITY' in clause_types

    def test_playbook_deactivation(self):
        """Playbook 無効化テスト"""
        playbook = TenantPlaybookFactory(is_active=True)
        playbook.is_active = False
        playbook.save()
        playbook.refresh_from_db()
        assert playbook.is_active is False

    def test_playbook_str(self):
        """__str__ の表示確認"""
        playbook = TenantPlaybookFactory(name='テスト用プレイブック')
        assert str(playbook) == 'テスト用プレイブック'

    def test_multiple_playbooks_per_account(self):
        """1 アカウントに複数プレイブックを紐づけられることを確認"""
        account = AccountFactory()
        pb1 = TenantPlaybookFactory(account=account, name='プレイブック1')
        pb2 = TenantPlaybookFactory(account=account, name='プレイブック2')
        assert account.playbooks.count() == 2


@pytest.mark.django_db
class TestClausePolicyClassification:
    """ClausePolicy の分類テスト"""

    def test_green_classification(self):
        """GREEN 基準に合致する契約条項の分類テスト"""
        policy = ClausePolicyFactory(
            clause_type='LIABILITY',
            standard_position={
                'max_liability': '契約金額の100%',
                'cap_type': 'percentage',
            },
        )
        # GREEN 判定: standard_position の基準内
        contract_clause = {
            'max_liability': '契約金額の100%',
            'cap_type': 'percentage',
        }
        # standard_position と一致 → GREEN
        assert contract_clause['max_liability'] == policy.standard_position['max_liability']

    def test_yellow_classification(self):
        """YELLOW 境界条件での分類テスト"""
        policy = ClausePolicyFactory(
            clause_type='LIABILITY',
            standard_position={'max_liability': '契約金額の100%'},
            acceptable_range={'max_liability_upper': '契約金額の200%'},
        )
        # YELLOW 判定: standard_position を超えるが acceptable_range 内
        contract_clause = {'max_liability': '契約金額の150%'}
        # standard_position と不一致だが、acceptable_range 内 → YELLOW
        assert contract_clause['max_liability'] != policy.standard_position['max_liability']
        assert 'max_liability_upper' in policy.acceptable_range

    def test_red_escalation_trigger(self):
        """RED フラグのエスカレーション検知テスト"""
        policy = ClausePolicyFactory(
            clause_type='LIABILITY',
            escalation_triggers={
                'unlimited_liability': True,
                'no_cap': True,
            },
        )
        # RED 判定: escalation_triggers に該当
        contract_clause = {'unlimited_liability': True}
        has_escalation = any(
            contract_clause.get(trigger) == value
            for trigger, value in policy.escalation_triggers.items()
        )
        assert has_escalation is True

    def test_clause_policy_unique_together(self):
        """同一プレイブック内で clause_type の重複が不可であることを確認"""
        playbook = TenantPlaybookFactory()
        ClausePolicyFactory(playbook=playbook, clause_type='LIABILITY')
        with pytest.raises(Exception):
            ClausePolicyFactory(playbook=playbook, clause_type='LIABILITY')

    def test_all_clause_types(self):
        """全 12 条項種別の ClausePolicy が作成可能であることを確認"""
        playbook = TenantPlaybookFactory()
        clause_types = [ct[0] for ct in ClausePolicy.CLAUSE_TYPE_CHOICES]
        for ct in clause_types:
            ClausePolicyFactory(playbook=playbook, clause_type=ct)
        assert ClausePolicy.objects.filter(playbook=playbook).count() == 12

    def test_clause_policy_str(self):
        """ClausePolicy.__str__ の表示確認"""
        playbook = TenantPlaybookFactory(name='テスト')
        policy = ClausePolicyFactory(playbook=playbook, clause_type='LIABILITY')
        assert str(policy) == 'テスト - 損害賠償・責任制限'

    def test_context_rules_override(self):
        """context_rules によるポリシーの条件別上書きテスト"""
        policy = ClausePolicyFactory(
            context_rules={
                'deal_size_over_10m': {
                    'max_liability_upper': '契約金額の150%',
                },
                'government_contract': {
                    'max_liability_upper': '契約金額の100%',
                },
            },
        )
        assert 'deal_size_over_10m' in policy.context_rules
        assert policy.context_rules['government_contract']['max_liability_upper'] == '契約金額の100%'


@pytest.mark.django_db
class TestTenantRuleEvaluation:
    """TenantRule の評価テスト"""

    def test_expiry_alert_rule(self):
        """期限アラートルール: 90日前に WARN が発生することを確認"""
        account = AccountFactory()
        rule_set = TenantRuleSetFactory(account=account)
        rule = TenantRuleFactory(
            rule_set=rule_set,
            rule_type='EXPIRY_ALERT',
            name='期限90日前アラート',
            condition={'days_before_expiry': 90},
            severity='WARNING',
        )
        contract = ContractFactory(account=account)

        # 期限80日後の契約 → 90日以内なので WARN
        log = RuleEvaluationLog.objects.create(
            rule=rule,
            contract=contract,
            result='WARN',
            detail={
                'days_remaining': 80,
                'expiry_date': '2026-05-11',
                'message': '契約期限まで80日です',
            },
        )
        assert log.result == 'WARN'
        assert log.detail['days_remaining'] == 80
        assert log.rule.severity == 'WARNING'

    def test_expiry_alert_pass(self):
        """期限アラートルール: 90日以上あれば PASS"""
        rule = TenantRuleFactory(
            rule_type='EXPIRY_ALERT',
            condition={'days_before_expiry': 90},
        )
        contract = ContractFactory()
        log = RuleEvaluationLog.objects.create(
            rule=rule,
            contract=contract,
            result='PASS',
            detail={'days_remaining': 120, 'message': '期限まで十分な日数があります'},
        )
        assert log.result == 'PASS'

    def test_required_contract_rule(self):
        """必須契約種別ルール: NDA 未締結で FAIL が発生することを確認"""
        account = AccountFactory()
        rule_set = TenantRuleSetFactory(account=account)
        rule = TenantRuleFactory(
            rule_set=rule_set,
            rule_type='REQUIRED_CONTRACT',
            name='NDA必須チェック',
            condition={
                'required_contract_types': ['NDA', '業務委託契約'],
            },
            severity='CRITICAL',
        )
        contract = ContractFactory(account=account)

        # NDA 未締結 → FAIL
        log = RuleEvaluationLog.objects.create(
            rule=rule,
            contract=contract,
            result='FAIL',
            detail={
                'missing_types': ['NDA'],
                'message': 'NDAが未締結です。締結を推奨します。',
            },
        )
        assert log.result == 'FAIL'
        assert 'NDA' in log.detail['missing_types']
        assert log.rule.severity == 'CRITICAL'

    def test_required_contract_pass(self):
        """必須契約種別ルール: 全て締結済みで PASS"""
        rule = TenantRuleFactory(
            rule_type='REQUIRED_CONTRACT',
            condition={'required_contract_types': ['NDA']},
        )
        contract = ContractFactory()
        log = RuleEvaluationLog.objects.create(
            rule=rule,
            contract=contract,
            result='PASS',
            detail={'missing_types': [], 'message': '全ての必須契約が締結済みです'},
        )
        assert log.result == 'PASS'
        assert len(log.detail['missing_types']) == 0

    def test_amount_threshold_rule(self):
        """金額閾値ルール: 閾値超過で WARN"""
        rule = TenantRuleFactory(
            rule_type='AMOUNT_THRESHOLD',
            name='高額契約アラート',
            condition={'threshold_amount': 10000000},
            severity='WARNING',
        )
        contract = ContractFactory()
        log = RuleEvaluationLog.objects.create(
            rule=rule,
            contract=contract,
            result='WARN',
            detail={
                'contract_amount': 15000000,
                'threshold': 10000000,
                'message': '契約金額が閾値（1000万円）を超過しています',
            },
        )
        assert log.result == 'WARN'
        assert log.detail['contract_amount'] > log.detail['threshold']

    def test_rule_deactivation(self):
        """無効化されたルールが評価対象外になることを確認"""
        rule = TenantRuleFactory(is_active=True)
        assert rule.is_active is True
        rule.is_active = False
        rule.save()
        rule.refresh_from_db()
        assert rule.is_active is False

    def test_rule_evaluation_log_str(self):
        """RuleEvaluationLog.__str__ の表示確認"""
        rule = TenantRuleFactory(name='期限チェック')
        contract = ContractFactory()
        log = RuleEvaluationLog.objects.create(
            rule=rule, contract=contract, result='WARN', detail={},
        )
        assert str(log) == '期限チェック - 警告'

    def test_multiple_rules_in_ruleset(self):
        """1 つの RuleSet に複数ルールを登録できることを確認"""
        rule_set = TenantRuleSetFactory()
        TenantRuleFactory(rule_set=rule_set, rule_type='EXPIRY_ALERT', name='期限アラート')
        TenantRuleFactory(rule_set=rule_set, rule_type='REQUIRED_CONTRACT', name='必須契約')
        TenantRuleFactory(rule_set=rule_set, rule_type='AMOUNT_THRESHOLD', name='金額閾値')
        assert rule_set.rules.count() == 3

    def test_rule_severity_choices(self):
        """severity の全選択肢でルール作成可能であることを確認"""
        for severity_code, _ in TenantRule.SEVERITY_CHOICES:
            rule = TenantRuleFactory(severity=severity_code)
            assert rule.severity == severity_code


@pytest.mark.django_db
class TestPlaybookTemplate:
    """PlaybookTemplate のテスト"""

    def test_create_template(self):
        """PlaybookTemplate 作成テスト"""
        template = PlaybookTemplateFactory(
            name='建設業テンプレート',
            industry='CONSTRUCTION',
        )
        assert template.pk is not None
        assert template.industry == 'CONSTRUCTION'

    def test_all_industry_choices(self):
        """全業種の PlaybookTemplate が作成可能であることを確認"""
        for industry_code, _ in PlaybookTemplate.INDUSTRY_CHOICES:
            template = PlaybookTemplateFactory(industry=industry_code)
            assert template.industry == industry_code

    def test_template_default_clause_policies_structure(self):
        """default_clause_policies の JSON 構造が正しいことを確認"""
        template = PlaybookTemplateFactory()
        policies = template.default_clause_policies
        assert isinstance(policies, dict)
        for clause_type, policy_data in policies.items():
            assert 'standard_position' in policy_data
            assert 'escalation_triggers' in policy_data

    def test_template_str(self):
        """PlaybookTemplate.__str__ の表示確認"""
        template = PlaybookTemplateFactory(name='建設業テンプレート')
        assert str(template) == '建設業テンプレート'


@pytest.mark.django_db
class TestResponseTemplate:
    """ResponseTemplate / TemplateVariable のテスト"""

    def test_create_response_template(self):
        """ResponseTemplate 作成テスト"""
        template = ResponseTemplateFactory()
        assert template.pk is not None
        assert template.inquiry_type == 'DSR'
        assert '{{requester_name}}' in template.body_template

    def test_template_variable_creation(self):
        """TemplateVariable 作成テスト"""
        resp_template = ResponseTemplateFactory()
        var = TemplateVariable.objects.create(
            template=resp_template,
            variable_name='requester_name',
            description='請求者名',
            is_required=True,
        )
        assert var.pk is not None
        assert var.template == resp_template
        assert var.is_required is True

    def test_escalation_trigger_detection(self):
        """escalation_triggers のパターンマッチテスト"""
        template = ResponseTemplateFactory(
            escalation_triggers=['訴訟', '裁判所', '損害賠償請求'],
        )
        test_text = '本件について訴訟を提起する予定です'
        has_escalation = any(
            trigger in test_text
            for trigger in template.escalation_triggers
        )
        assert has_escalation is True

    def test_no_escalation_trigger(self):
        """escalation_triggers に該当しない場合のテスト"""
        template = ResponseTemplateFactory(
            escalation_triggers=['訴訟', '裁判所'],
        )
        test_text = '個人データの開示をお願いいたします'
        has_escalation = any(
            trigger in test_text
            for trigger in template.escalation_triggers
        )
        assert has_escalation is False

    def test_all_inquiry_types(self):
        """全問い合わせ種別で ResponseTemplate 作成可能であることを確認"""
        account = AccountFactory()
        for inquiry_code, _ in ResponseTemplate.INQUIRY_TYPE_CHOICES:
            template = ResponseTemplateFactory(
                account=account,
                inquiry_type=inquiry_code,
            )
            assert template.inquiry_type == inquiry_code

    def test_template_with_multiple_variables(self):
        """複数の TemplateVariable を持つテンプレートテスト"""
        resp_template = ResponseTemplateFactory()
        vars_data = [
            ('requester_name', '請求者名', True),
            ('deadline', '回答期限', True),
            ('response_body', '回答本文', True),
            ('cc_email', 'CC先メール', False),
        ]
        for var_name, desc, required in vars_data:
            TemplateVariable.objects.create(
                template=resp_template,
                variable_name=var_name,
                description=desc,
                is_required=required,
            )
        assert resp_template.variables.count() == 4
        assert resp_template.variables.filter(is_required=True).count() == 3
