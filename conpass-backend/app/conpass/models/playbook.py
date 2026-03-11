from django.db import models


class PlaybookTemplate(models.Model):
    """
    プレイブックテンプレート
    業界別のデフォルト条項ポリシーを定義
    """

    INDUSTRY_CHOICES = [
        ('CONSTRUCTION', '建設業'),
        ('REAL_ESTATE', '不動産'),
        ('IT', 'IT・SaaS'),
        ('MEDICAL', '医療・介護'),
        ('ACCOUNTANT', '税理士事務所'),
        ('LAWYER', '弁護士事務所'),
        ('GENERAL', '汎用'),
    ]

    name = models.CharField(max_length=100)
    industry = models.CharField(max_length=30, choices=INDUSTRY_CHOICES)
    description = models.TextField(blank=True)
    default_clause_policies = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class TenantPlaybook(models.Model):
    """
    テナントプレイブック
    アカウントごとのプレイブック設定
    """

    YOUR_SIDE_CHOICES = [
        ('VENDOR', 'ベンダー・供給者'),
        ('CUSTOMER', '顧客・購買者'),
        ('LICENSOR', 'ライセンサー'),
        ('LICENSEE', 'ライセンシー'),
        ('PARTNER', 'パートナー'),
    ]

    account = models.ForeignKey('Account', on_delete=models.CASCADE, related_name='playbooks')
    name = models.CharField(max_length=100)
    template = models.ForeignKey(PlaybookTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    your_side = models.CharField(max_length=20, choices=YOUR_SIDE_CHOICES, default='VENDOR')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ClausePolicy(models.Model):
    """
    条項ポリシー
    プレイブックに紐づく条項種別ごとの評価基準
    """

    CLAUSE_TYPE_CHOICES = [
        ('LIABILITY', '損害賠償・責任制限'),
        ('INDEMNIFICATION', '補償・免責'),
        ('IP', '知的財産権'),
        ('DATA_PROTECTION', 'データ保護・個人情報'),
        ('CONFIDENTIALITY', '守秘義務'),
        ('WARRANTY', '保証・表明'),
        ('TERMINATION', '解除・終了'),
        ('GOVERNING_LAW', '準拠法・管轄'),
        ('INSURANCE', '保険'),
        ('ASSIGNMENT', '譲渡'),
        ('FORCE_MAJEURE', '不可抗力'),
        ('PAYMENT', '支払条件'),
    ]

    playbook = models.ForeignKey(TenantPlaybook, on_delete=models.CASCADE, related_name='clause_policies')
    clause_type = models.CharField(max_length=30, choices=CLAUSE_TYPE_CHOICES)
    standard_position = models.JSONField(default=dict, help_text='GREEN: 理想の文言・条件範囲')
    acceptable_range = models.JSONField(default=dict, help_text='YELLOW: 交渉可能な範囲')
    escalation_triggers = models.JSONField(default=dict, help_text='RED: エスカレーションフラグ')
    context_rules = models.JSONField(default=dict, help_text='deal_size等による適用変更')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('playbook', 'clause_type')

    def __str__(self):
        return f"{self.playbook.name} - {self.get_clause_type_display()}"


class TenantRuleSet(models.Model):
    """
    テナントルールセット
    アカウントごとのルールグループ
    """

    account = models.ForeignKey('Account', on_delete=models.CASCADE, related_name='rule_sets')
    name = models.CharField(max_length=100)
    playbook = models.ForeignKey(TenantPlaybook, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class TenantRule(models.Model):
    """
    テナントルール
    個別の評価ルール定義
    """

    RULE_TYPE_CHOICES = [
        ('EXPIRY_ALERT', '期限アラート'),
        ('REQUIRED_CONTRACT', '必須契約種別'),
        ('AMOUNT_THRESHOLD', '金額閾値'),
        ('BENCHMARK_DEVIATION', 'ベンチマーク逸脱'),
        ('LAW_UPDATE', '法令改正'),
        ('CUSTOM_AI', 'AIカスタム評価'),
    ]

    SEVERITY_CHOICES = [
        ('INFO', '情報'),
        ('WARNING', '警告'),
        ('CRITICAL', '緊急'),
    ]

    rule_set = models.ForeignKey(TenantRuleSet, on_delete=models.CASCADE, related_name='rules')
    rule_type = models.CharField(max_length=30, choices=RULE_TYPE_CHOICES)
    name = models.CharField(max_length=100)
    condition = models.JSONField(default=dict)
    action = models.JSONField(default=dict)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='WARNING')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class RuleEvaluationLog(models.Model):
    """
    ルール評価ログ
    ルール実行結果の記録
    """

    RESULT_CHOICES = [
        ('PASS', 'パス'),
        ('WARN', '警告'),
        ('FAIL', '失敗'),
    ]

    rule = models.ForeignKey(TenantRule, on_delete=models.CASCADE, related_name='evaluation_logs')
    contract = models.ForeignKey('Contract', on_delete=models.CASCADE, related_name='rule_evaluations')
    evaluated_at = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=10, choices=RESULT_CHOICES)
    detail = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.rule.name} - {self.get_result_display()}"


class ResponseTemplate(models.Model):
    """
    回答テンプレート
    問い合わせ種別ごとの定型回答テンプレート
    """

    INQUIRY_TYPE_CHOICES = [
        ('DSR', 'データ主体リクエスト'),
        ('HOLD', '訴訟ホールド'),
        ('VENDOR', 'ベンダー質問'),
        ('NDA', 'NDAリクエスト'),
        ('PRIVACY', 'プライバシー照会'),
        ('SUBPOENA', '召喚状・法的手続き'),
        ('CUSTOM', 'カスタム'),
    ]

    account = models.ForeignKey('Account', on_delete=models.CASCADE, related_name='response_templates')
    inquiry_type = models.CharField(max_length=20, choices=INQUIRY_TYPE_CHOICES)
    name = models.CharField(max_length=100)
    subject_template = models.CharField(max_length=200)
    body_template = models.TextField()
    escalation_triggers = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class TemplateVariable(models.Model):
    """
    テンプレート変数
    回答テンプレートで使用する変数定義
    """

    template = models.ForeignKey(ResponseTemplate, on_delete=models.CASCADE, related_name='variables')
    variable_name = models.CharField(max_length=50)
    description = models.CharField(max_length=200)
    is_required = models.BooleanField(default=True)

    def __str__(self):
        return self.variable_name
