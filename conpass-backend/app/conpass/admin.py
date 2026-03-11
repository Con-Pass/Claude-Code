from django.contrib import admin

# Register your models here.
from conpass.models import (
    Account, Corporate, SocialLogin, Group, Client, User, Directory, DirectoryPermission, File,
    Contract, AdobeSign, AccountStorageSummary, ArticleLibrary, ContractHistory, ContractBody, ContractPrediction,
    ContractTemplateInsertKey, ContractTemplateInsert, Information, MetaKey, MetaData, PermissionTarget, Permission,
    WorkflowTaskMaster, WorkflowParamKey, WorkflowParam, Workflow, WorkflowStep, WorkflowStepComment, WorkflowTask,
    WorkflowTaskUser, AdobeSetting, AdobeSignApprovalUser,
    PlaybookTemplate, TenantPlaybook, ClausePolicy, TenantRuleSet, TenantRule, RuleEvaluationLog,
    ResponseTemplate, TemplateVariable,
    GmoSign, GmoSignSigner)
from django.contrib.auth.admin import UserAdmin


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """
    アカウント管理
    """
    pass


@admin.register(Corporate)
class CorporateAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(SocialLogin)
class SocialLoginAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(User)
class UserAdmin(UserAdmin):
    """
    管理
    """
    pass


@admin.register(Directory)
class DirectoryAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(DirectoryPermission)
class DirectoryPermissionAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(AdobeSign)
class AdobeSignAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(AccountStorageSummary)
class AccountStorageSummaryAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(ArticleLibrary)
class ArticleLibraryAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(ContractHistory)
class ContractHistoryAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(ContractBody)
class ContractBodyAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(ContractPrediction)
class ContractPredictionAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(ContractTemplateInsertKey)
class ContractTemplateInsertKeyAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(ContractTemplateInsert)
class ContractTemplateInsertAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(Information)
class InformationAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(MetaKey)
class MetaKeyAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(MetaData)
class MetaDataAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(PermissionTarget)
class PermissionTargetAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(WorkflowTaskMaster)
class WorkflowTaskMasterAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(WorkflowParamKey)
class WorkflowParamKeyAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(WorkflowParam)
class WorkflowParamAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(WorkflowStep)
class WorkflowStepAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(WorkflowStepComment)
class WorkflowStepCommentAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(WorkflowTask)
class WorkflowTaskAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(WorkflowTaskUser)
class WorkflowTaskUserAdmin(admin.ModelAdmin):
    """
    管理
    """
    pass


@admin.register(PlaybookTemplate)
class PlaybookTemplateAdmin(admin.ModelAdmin):
    """
    プレイブックテンプレート管理
    """
    list_display = ('name', 'industry', 'created_at')
    list_filter = ('industry',)


@admin.register(TenantPlaybook)
class TenantPlaybookAdmin(admin.ModelAdmin):
    """
    テナントプレイブック管理
    """
    list_display = ('name', 'account', 'your_side', 'is_active', 'created_at')
    list_filter = ('your_side', 'is_active')


@admin.register(ClausePolicy)
class ClausePolicyAdmin(admin.ModelAdmin):
    """
    条項ポリシー管理
    """
    list_display = ('playbook', 'clause_type', 'created_at')
    list_filter = ('clause_type',)


@admin.register(TenantRuleSet)
class TenantRuleSetAdmin(admin.ModelAdmin):
    """
    テナントルールセット管理
    """
    list_display = ('name', 'account', 'is_active', 'created_at')
    list_filter = ('is_active',)


@admin.register(TenantRule)
class TenantRuleAdmin(admin.ModelAdmin):
    """
    テナントルール管理
    """
    list_display = ('name', 'rule_set', 'rule_type', 'severity', 'is_active')
    list_filter = ('rule_type', 'severity', 'is_active')


@admin.register(RuleEvaluationLog)
class RuleEvaluationLogAdmin(admin.ModelAdmin):
    """
    ルール評価ログ管理
    """
    list_display = ('rule', 'contract', 'result', 'evaluated_at')
    list_filter = ('result',)


@admin.register(ResponseTemplate)
class ResponseTemplateAdmin(admin.ModelAdmin):
    """
    回答テンプレート管理
    """
    list_display = ('name', 'account', 'inquiry_type', 'is_active', 'created_at')
    list_filter = ('inquiry_type', 'is_active')


@admin.register(TemplateVariable)
class TemplateVariableAdmin(admin.ModelAdmin):
    """
    テンプレート変数管理
    """
    list_display = ('variable_name', 'template', 'is_required')
    list_filter = ('is_required',)


@admin.register(GmoSign)
class GmoSignAdmin(admin.ModelAdmin):
    """
    GMO Sign管理
    """
    list_display = ('gmo_document_id', 'contract', 'status', 'sent_at', 'signed_at', 'created_at')
    list_filter = ('status',)


@admin.register(GmoSignSigner)
class GmoSignSignerAdmin(admin.ModelAdmin):
    """
    GMO Sign署名者管理
    """
    list_display = ('name', 'email', 'gmo_sign', 'order', 'status', 'signed_at')
    list_filter = ('status',)
