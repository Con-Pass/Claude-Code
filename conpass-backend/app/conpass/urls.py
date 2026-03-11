from django.urls import path
from conpass.views.local_file_view import LocalFileView

from common.auth.views import LoginView, LogoutView, SocialLoginView, SsoLoginView
from conpass import views
from conpass.views.account_active_summary.views import AccountActiveSummaryListView
from conpass.views.account_storage_summary.views import AccountStorageSummaryListView
from conpass.views.contract.export_pdf_views import ExportPdfView
from conpass.views.contract.export_word_views import ExportWordView
from conpass.views.file.views import FileListView, FileLinkedContractListView, FileUploadStatusListView, \
    FileLinkedContractDeleteView
from conpass.views.gcp.prediction import GoogleCloudPredictionView
from conpass.views.gcp.vision import GoogleCloudVisionImageView, GoogleCloudVisionPdfView
from conpass.views.password_reset.view import PasswordResetMailView
from conpass.views.sys.account_storage_summary.views import SysAccountStorageSummaryListView
from conpass.views.sys.workflow.views import SysWorkflowEditView, SysWorkflowCloneDataView, SysWorkflowDataListView, \
    SysWorkflowAllDataView, SysSortWorkflowListView, SysWorkflowDeleteView
from conpass.views.upload.views import UploadContractFileView, UploadFileLinkedContractView, UploadContractUrlView, \
    NotifyUploadedToGcsView
from conpass.views.views import UserView, DelayView, SysUserView
from conpass.views.corporate.view import SortCorporateListView, CorporateListDeleteView, CorporateDetailView, \
    CorporateEditView
from conpass.views.client.view import ClientListView, ClientListDeleteView, ClientEditView, ClientDetailView, \
    SortClientListView, ClientServiceListView, ClientCsvUploadView
from conpass.views.contract.aggregate_view import ContractMetaAggregateView
from conpass.views.contract.views import ListView as contractListView, ContractMetaDataListView, \
    ContractWithMetaListView, ContractZipDownload, ContractDataList, ContractDirectoryList, ContractDirectoryUpdate, \
    ContractBodyListView, PaginateView as contractPaginateView, ContractChildsView, ContractCommentView, ContractCommentDeleteView, \
    ContractMetaDataView, ContractOpen, AccountContractsView, RelatedContractsView, UpdateContractRenewNotify, \
    ContractBodyDiffHtmlView, ContractMentionView, ContractPageSize, ContractBodyVersionAdoptView, ContractMetaKeyFreeList, \
    ContractMetadataCsvDownload, ContractMetadataCsvUpload, ContractBlankMetadataCsvDownload
from conpass.views.contract.views import ItemView as contractItemView
from conpass.views.contract.views import BodyView as contractBodyItemView
from conpass.views.contract.views import BodySaveView as contractBodySaveView
from conpass.views.contract.views import CreateContractArchive, ContractArchiveList, ContractArchiveRecent, DeleteContractArchives, \
    ContractSearchSettingList, ContractCancel, ContractExpire, ContractReturn, ContractGarbageUpdate, ContractGarbageDelete
from conpass.views.setting.views import SettingMetaView, SettingMetaUpdateView, SettingMetaCSVUpdateView, \
    SettingMetaCSVDownloadView, SettingMetaDirectoryView, DirectoryMetaView, DirectoryMetaUpdateView, SettingContractMetaCSVDownloadView
from conpass.views.gcp.cloud_storage import GoogleCloudStorageUpload, GoogleCloudStorageDownload, GoogleCloudStoragePreview, \
    GoogleCloudStorageFileInfo, \
    GoogleCloudStorageFileList, GoogleCloudStorageUploadBlob, GoogleCloudStorageDeleteFiles, GoogleCloudStorageFileLinkedContractDeleteView
from conpass.views.template_json.view import TemplateJsonView
from conpass.views.user.view import UserDeleteView, UserDetailView, UserEditView, SortUserListView, \
    UserDataListView, UserClientCsvUpload, UserPermissionsView, UserPermissionsListView, UserCsvUpload, \
    UserPermissionCategorySetView, UserPermissionsCategoryListView, PermissionsCategoryDeleteView, UserPagePermissionCategoryView
from conpass.views.anyflow.view import UserInfoView
from conpass.views.account.views import AccountLinkView, AccountSpSettingsView, AccountIdpSettingsView
from conpass.views.sys.account.view import SysAccountListView, SysAccountDetailView, SysAccountDeleteView, \
    SysAccountEditView, SysAccountCreateView, SysAccountListDownloadView
from conpass.views.sys.user.view import SysUserListView, SysUserDetailView, SysUserDeleteView, \
    SysUserEditView, SysUserTypeListView, SysBPOUserDetailView
from conpass.views.bpo.view import BpoCreateView, BpoCorrectionView, BpoCorrectionCompleteView
from conpass.views.dashboard.view import DashboardInfoListView
from conpass.views.sys.bpo.view import SysBpoListView, SysBpoDetailView, SysBpoCorrectionListView, SysBpoCorrectionDetailView
from conpass.views.sys.login.views import SysLoginView, SysLogoutView
from conpass.views.support.views import SupportRequestView
from conpass.views.sys.support.views import SysSupportListView, SysSupportDetailView
from conpass.views.sys.info.view import SysInfoListView, SysInfoDetailView, SysInfoEditView
from conpass.views.group.view import GroupListView, GroupUserListView, GroupDeleteView, GroupDetailView, \
    GroupEditView, SortGroupListView, GroupPermissionView
from conpass.views.sys.group.view import SysGroupListView, SysGroupUserListView, SysGroupDeleteView, SysGroupDetailView, \
    SysGroupEditView, SysGroupAccountListView
from conpass.views.notificationsetting.view import NotificationSettingView, NotificationSettingEditView
from conpass.views.sys.corporate.view import SysCorporateListView, SysCorporateDetailView
from conpass.views.directory.views import DirectoryListView, DirectoryMenuListView, DirectoryDeleteView, \
    DirectoryDetailView, DirectoryUpdateView, DirectoryChildListView, DirectoryCheckDeleteView, DirectoryAllowedListView, \
    DirectorySortEditView
from conpass.views.workflow.views import WorkflowTaskMasterListView, WorkflowEditView, SortWorkflowListView, \
    WorkflowAllDataView, WorkflowCloneDataView, WorkflowStepDataView, WorkflowStartView, WorkflowAddStepCommentView, \
    WorkflowFinishTaskUserView, WorkflowRejectStepView, WorkflowNotificationListView, WorkflowDeleteView, \
    WorkflowDataListView
from conpass.views.mailtemplate.view import MailTemplateListView, MailTagListView, MailTemplateEditView, \
    MailTemplatePreviewView
from conpass.views.adobesign.view import AdobeSignConfirmView, AdobeSignCertificationView, \
    AdobeSignCertificationAuthView, \
    AdobeSignCreateWebhookView, AdobeSignWebhookView, AdobeSignGetBaseURIView
from conpass.views.sys.upload.views import SysUploadLoginAdFileView
from conpass.views.sys.admin import view as admin
from conpass.views.ip_address.view import SortIpAddressListView, IpAddressDetailView, IpAddressEditView, \
    IpAddressDeleteView, IpAddressGetView
from conpass.views.conversation.view import ConversationListView, ConversationCreateView, ConversationDeleteView, \
    ConversationDeleteAllView, ConversationFetchView, UploadWordFileView
from conpass.views.conversation_comment.view import CommentEditView, CommentDeleteView
from conpass.views.gmo_sign.view import (
    GmoSignListView, GmoSignCreateView, GmoSignSendView,
    GmoSignStatusView, GmoSignCancelView, GmoSignWebhookView,
)
from conpass.views.playbook.views import (
    PlaybookTemplateListView,
    TenantPlaybookListView, TenantPlaybookCreateView, TenantPlaybookUpdateView,
    TenantPlaybookDeleteView, TenantPlaybookApplyTemplateView,
    ClausePolicyListView, ClausePolicyDetailView,
    TenantRuleListView, TenantRuleDetailView, TenantRuleAlertsView,
    ResponseTemplateListView, ResponseTemplateDetailView,
)
from conpass.views.compliance.views import (
    ComplianceRescoreView, LawChangeHookView, ComplianceScoreSummaryView,
)
from conpass.views.contract.rescan_view import ContractRescanView, ContractExtractionStatusView
from conpass.views.setting.law_view import LawListView, LawDetailView, LawReindexView, LawFileDownloadView, LawFileDeleteView
from conpass.views.contract.relation_view import ContractRelationsView, ContractParentView

urlpatterns = [
    path('', views.IndexView.as_view()),
    # path('api-token-auth', obtain_auth_token),
    path('add', DelayView.as_view()),
    path('auth/login', LoginView.as_view()),
    path('auth/sociallogin', SocialLoginView.as_view()),
    path('auth/ssologin', SsoLoginView.as_view()),
    path('auth/logout', LogoutView.as_view()),
    path('account-storage-summary/list', AccountStorageSummaryListView.as_view()),
    path('account-active-summary/list', AccountActiveSummaryListView.as_view()),
    path('user', UserView.as_view()),
    path('user/data/list', UserDataListView.as_view()),
    path('user/permission/list', UserPermissionsView.as_view()),
    path('user/list/permission/list', UserPermissionsListView.as_view()),
    path('user/permission/set', UserPermissionCategorySetView.as_view()),
    path('user/list/permissioncategory/list', UserPagePermissionCategoryView.as_view()),
    path('dashboard', views.Dashboard.as_view()),
    path('dashboard/info/list', DashboardInfoListView.as_view()),
    path('corporate/all', SortCorporateListView.as_view()),
    path('corporate/delete', CorporateListDeleteView.as_view()),
    path('corporate/detail', CorporateDetailView.as_view()),
    path('corporate/edit', CorporateEditView.as_view()),
    path('contract', contractItemView.as_view()),
    path('contract/all', contractListView.as_view()),
    path('contract/paginate', contractPaginateView.as_view()),
    path('contract/comment', ContractCommentView.as_view()),
    path('contract/comment/delete', ContractCommentDeleteView.as_view()),
    path('contract/mention', ContractMentionView.as_view()),
    path('contract/body', contractBodyItemView.as_view()),  # get
    path('contract/body/add', contractBodySaveView.as_view()),  # post
    path('contract/body/list', ContractBodyListView.as_view()),
    path('contract/body/version/adopt', ContractBodyVersionAdoptView.as_view()),
    path('contract/body/diff', ContractBodyDiffHtmlView.as_view()),
    path('contract/metadata/aggregate', ContractMetaAggregateView.as_view()),
    path('contract/metadata', ContractMetaDataListView.as_view()),
    path('contract/metadata/<int:metadata_id>', ContractMetaDataView.as_view()),
    path('contract/<int:contract_id>/metadata', ContractMetaDataListView.as_view()),
    path('contract/<int:contract_id>/rescan', ContractRescanView.as_view()),
    path('contract/<int:contract_id>/extraction-status', ContractExtractionStatusView.as_view()),
    path('contract/export/pdf', ExportPdfView.as_view()),
    path('contract/export/word', ExportWordView.as_view()),
    path('contract/archive/create', CreateContractArchive.as_view()),
    path('contract/archive/list', ContractArchiveList.as_view()),
    path('contract/archive/recent', ContractArchiveRecent.as_view()),
    path('contract/archive/delete', DeleteContractArchives.as_view()),
    path('contract/data/meta/list', ContractWithMetaListView.as_view()),
    path('contract/renewnotify', UpdateContractRenewNotify.as_view()),
    path('contract/data/list', ContractDataList.as_view()),
    path('contract/export/zip', ContractZipDownload.as_view()),
    path('contract/search/setting', ContractSearchSettingList.as_view()),
    path('contract/directory/list', ContractDirectoryList.as_view()),
    path('contract/directory/update', ContractDirectoryUpdate.as_view()),
    path('contract/cancel', ContractCancel.as_view()),
    path('contract/expire', ContractExpire.as_view()),
    path('contract/return', ContractReturn.as_view()),
    path('contract/pagesize', ContractPageSize.as_view()),
    path('contract/garbage/update', ContractGarbageUpdate.as_view()),
    path('contract/garbage/delete', ContractGarbageDelete.as_view()),
    path('contract/open', ContractOpen.as_view()),
    path('contract/childs', ContractChildsView.as_view()),
    path('contract/account/<int:contract_id>/', AccountContractsView.as_view()),
    path('contract/related/<int:contract_id>/', RelatedContractsView.as_view()),
    path('contract/<int:contract_id>/relations/', ContractRelationsView.as_view()),
    path('contract/<int:contract_id>/parent/', ContractParentView.as_view()),
    path('contract/metakey/free', ContractMetaKeyFreeList.as_view()),
    path('contract/meta/csv/download', ContractMetadataCsvDownload.as_view()),
    path('contract/meta/blank/csv/download', ContractBlankMetadataCsvDownload.as_view()),
    path('contract/meta/csv/upload', ContractMetadataCsvUpload.as_view()),
    path('client/all', SortClientListView.as_view()),
    path('client/data/all', ClientServiceListView.as_view()),
    path('client/delete', ClientListDeleteView.as_view()),
    path('clientEdit/', ClientEditView.as_view()),
    path('clientDetail/', ClientDetailView.as_view()),
    path('client/csv-upload', ClientCsvUploadView.as_view()),
    path('setting/meta', SettingMetaView.as_view()),
    path('setting/meta/update', SettingMetaUpdateView.as_view()),
    path('setting/meta/csv/update', SettingMetaCSVUpdateView.as_view()),
    path('setting/meta/csv/download', SettingMetaCSVDownloadView.as_view()),
    path('setting/contract/meta/csv/download', SettingContractMetaCSVDownloadView.as_view()),
    path('setting/meta/directory', SettingMetaDirectoryView.as_view()),
    path('setting/directory/meta', DirectoryMetaView.as_view()),
    path('setting/directory/meta/update', DirectoryMetaUpdateView.as_view()),
    path('setting/directory/all', DirectoryListView.as_view()),
    path('setting/directory/menu/all', DirectoryMenuListView.as_view()),
    path('setting/directory/delete', DirectoryDeleteView.as_view()),
    path('setting/directory/update', DirectoryUpdateView.as_view()),
    path('setting/directory/sort/edit', DirectorySortEditView.as_view()),
    path('setting/directory/detail', DirectoryDetailView.as_view()),
    path('setting/directory/child/all', DirectoryChildListView.as_view()),
    path('setting/directory/check/delete', DirectoryCheckDeleteView.as_view()),
    path('setting/directory/list/allowed', DirectoryAllowedListView.as_view()),
    path('setting/mail/template/list', MailTemplateListView.as_view()),
    path('setting/mail/template/edit', MailTemplateEditView.as_view()),
    path('setting/mail/template/preview', MailTemplatePreviewView.as_view()),
    path('setting/mail/tag/list', MailTagListView.as_view()),
    path('setting/notification/all', NotificationSettingView.as_view()),
    path('setting/notification/edit', NotificationSettingEditView.as_view()),
    path('setting/adobe/sign/confirm', AdobeSignConfirmView.as_view()),
    path('setting/adobe/sign/certification', AdobeSignCertificationView.as_view()),
    path('setting/adobe/sign/certification/auth', AdobeSignCertificationAuthView.as_view()),
    path('setting/adobe/sign/baseuris', AdobeSignGetBaseURIView.as_view()),
    path('setting/adobe/sign/create/webhook', AdobeSignCreateWebhookView.as_view()),
    path('setting/adobe/sign/webhook', AdobeSignWebhookView.as_view()),
    path('setting/permission-category/list', UserPermissionsCategoryListView.as_view()),  # カテゴリーのリストとアップデート
    path('setting/permission-category/delete', PermissionsCategoryDeleteView.as_view()),  # カテゴリーの削除
    path('gcs/upload', GoogleCloudStorageUpload.as_view()),
    path('gcs/upload/blob', GoogleCloudStorageUploadBlob.as_view()),
    path('gcs/download', GoogleCloudStorageDownload.as_view()),
    path('gcs/preview', GoogleCloudStoragePreview.as_view()),
    path('gcs/delete', GoogleCloudStorageDeleteFiles.as_view()),
    path('gcs/file/info', GoogleCloudStorageFileInfo.as_view()),
    path('gcs/file/all', GoogleCloudStorageFileList.as_view()),
    path('gcs/liked/delete', GoogleCloudStorageFileLinkedContractDeleteView.as_view()),
    path('gcp/prediction', GoogleCloudPredictionView.as_view()),
    path('gcp/vision/image', GoogleCloudVisionImageView.as_view()),
    path('gcp/vision/pdf', GoogleCloudVisionPdfView.as_view()),
    path('file/all', FileListView.as_view()),
    path('file/contract/linked/all', FileLinkedContractListView.as_view()),
    path('file/contract/linked/delete', FileLinkedContractDeleteView.as_view()),
    path('fileuploadstatus/all', FileUploadStatusListView.as_view()),
    path('upload/contract', UploadContractFileView.as_view()),
    path('upload/contract/linked/file', UploadFileLinkedContractView.as_view()),
    path('upload/upload_url', UploadContractUrlView.as_view()),
    path('notify/uploaded-to-gcs', NotifyUploadedToGcsView.as_view()),
    path('user/all', SortUserListView.as_view()),
    path('user/delete', UserDeleteView.as_view()),
    path('userDetail/', UserDetailView.as_view()),
    path('userEdit/', UserEditView.as_view()),
    path('user/client/<int:client_id>/csv-upload', UserClientCsvUpload.as_view()),
    path('user/upload', UserCsvUpload.as_view()),
    path('account/link', AccountLinkView.as_view()),
    path('account/sp-settings', AccountSpSettingsView.as_view()),
    path('account/idp-settings', AccountIdpSettingsView.as_view()),
    path('support/request', SupportRequestView.as_view()),
    path('bpo/create', BpoCreateView.as_view()),
    path('bpo-correction/create', BpoCorrectionView.as_view()),
    path('bpo-correction/complete', BpoCorrectionCompleteView.as_view()),
    path('workflow/taskmaster/all', WorkflowTaskMasterListView.as_view()),
    path('workflow/all', SortWorkflowListView.as_view()),   # paginate
    path('workflow/edit', WorkflowEditView.as_view()),
    path('workflow/delete', WorkflowDeleteView.as_view()),
    path('workflow/data/all', WorkflowAllDataView.as_view()),
    path('workflow/data/step', WorkflowStepDataView.as_view()),
    path('workflow/data/clone', WorkflowCloneDataView.as_view()),
    path('workflow/data/list', WorkflowDataListView.as_view()),
    path('workflow/start', WorkflowStartView.as_view()),
    path('workflow/step/comment', WorkflowAddStepCommentView.as_view()),
    path('workflow/step/reject', WorkflowRejectStepView.as_view()),
    path('workflow/task/user/finish', WorkflowFinishTaskUserView.as_view()),
    path('workflow/notification/list', WorkflowNotificationListView.as_view()),
    path('password_reset_mail/', PasswordResetMailView.as_view()),
    path('sys/login', SysLoginView.as_view()),
    path('sys/logout', SysLogoutView.as_view()),
    path('sys/admin/all', admin.SysAdminListView.as_view()),
    path('sys/admin/delete', admin.SysAdminDeleteView.as_view()),
    path('sys/admin/detail', admin.SysAdminDetailView.as_view()),
    path('sys/admin/new', admin.SysAdminNewView.as_view()),
    path('sys/admin/edit', admin.SysAdminEditView.as_view()),
    path('sys/account/all', SysAccountListView.as_view()),
    path('sys/account/download', SysAccountListDownloadView.as_view()),
    path('sys/account/delete', SysAccountDeleteView.as_view()),
    path('sys/account/detail', SysAccountDetailView.as_view()),
    path('sys/account/edit', SysAccountEditView.as_view()),
    path('sys/account/create', SysAccountCreateView.as_view()),
    path('sys/account-storage-summary/<int:account_id>', SysAccountStorageSummaryListView.as_view()),
    path('sys/user', SysUserView.as_view()),
    path('sys/user/all', SysUserListView.as_view()),
    path('sys/user/delete', SysUserDeleteView.as_view()),
    path('sys/user/detail', SysUserDetailView.as_view()),
    path('sys/user/bpo/detail', SysBPOUserDetailView.as_view()),
    path('sys/user/edit/', SysUserEditView.as_view()),
    path('sys/user/type/list/', SysUserTypeListView.as_view()),
    path('sys/bpo/list', SysBpoListView.as_view()),
    path('sys/bpo/detail', SysBpoDetailView.as_view()),
    path('sys/bpo-correction/list', SysBpoCorrectionListView.as_view()),
    path('sys/bpo-correction/detail', SysBpoCorrectionDetailView.as_view()),
    path('sys/support/list', SysSupportListView.as_view()),
    path('sys/support/detail', SysSupportDetailView.as_view()),
    path('sys/info/list', SysInfoListView.as_view()),
    path('sys/info/detail', SysInfoDetailView.as_view()),
    path('sys/info/edit', SysInfoEditView.as_view()),
    path('group/all', SortGroupListView.as_view()),
    path('group/list', GroupListView.as_view()),
    path('group/user/all', GroupUserListView.as_view()),
    path('group/delete', GroupDeleteView.as_view()),
    path('group/detail', GroupDetailView.as_view()),
    path('group/edit', GroupEditView.as_view()),
    path('group/permission', GroupPermissionView.as_view()),
    path('sys/group/all', SysGroupListView.as_view()),
    path('sys/group/user/all', SysGroupUserListView.as_view()),
    path('sys/group/delete', SysGroupDeleteView.as_view()),
    path('sys/group/detail', SysGroupDetailView.as_view()),
    path('sys/group/edit', SysGroupEditView.as_view()),
    path('sys/group/account/all', SysGroupAccountListView.as_view()),
    path('sys/corporate/all', SysCorporateListView.as_view()),
    path('sys/corporate/detail', SysCorporateDetailView.as_view()),
    path('sys/upload/loginad', SysUploadLoginAdFileView.as_view()),
    path('sys/workflow/edit', SysWorkflowEditView.as_view()),
    path('sys/workflow/all', SysSortWorkflowListView.as_view()),  # paginate
    path('sys/workflow/data/clone', SysWorkflowCloneDataView.as_view()),
    path('sys/workflow/data/list', SysWorkflowDataListView.as_view()),
    path('sys/workflow/data/all', SysWorkflowAllDataView.as_view()),
    path('sys/workflow/delete', SysWorkflowDeleteView.as_view()),
    path('template/json', TemplateJsonView.as_view()),
    path('ip-address/all', SortIpAddressListView.as_view()),
    path('ip-address/detail', IpAddressDetailView.as_view()),
    path('ip-address/edit', IpAddressEditView.as_view()),
    path('ip-address/delete', IpAddressDeleteView.as_view()),
    path('ip-address/get', IpAddressGetView.as_view()),
    path('anyflow/userinfo', UserInfoView.as_view()),
    path('conversation/list', ConversationListView.as_view()),
    path('conversation/delete', ConversationDeleteView.as_view()),
    path('conversation/delete/all', ConversationDeleteAllView.as_view()),
    path('conversation/create', ConversationCreateView.as_view()),
    path('conversation/comment/edit', CommentEditView.as_view()),
    path('conversation/comment/delete', CommentDeleteView.as_view()),
    path('conversation/fetch', ConversationFetchView.as_view()),
    path('conversation/upload', UploadWordFileView.as_view()),
    # GMO Sign API
    path('gmo-sign/list', GmoSignListView.as_view()),
    path('gmo-sign/create', GmoSignCreateView.as_view()),
    path('gmo-sign/send', GmoSignSendView.as_view()),
    path('gmo-sign/<int:gmo_sign_id>/status', GmoSignStatusView.as_view()),
    path('gmo-sign/<int:gmo_sign_id>/cancel', GmoSignCancelView.as_view()),
    path('gmo-sign/webhook', GmoSignWebhookView.as_view()),
    # Playbook API
    path('tenant/playbook/templates', PlaybookTemplateListView.as_view()),
    path('tenant/playbook', TenantPlaybookListView.as_view()),
    path('tenant/playbook/create', TenantPlaybookCreateView.as_view()),
    path('tenant/playbook/<int:playbook_id>/update', TenantPlaybookUpdateView.as_view()),
    path('tenant/playbook/<int:playbook_id>/delete', TenantPlaybookDeleteView.as_view()),
    path('tenant/playbook/<int:playbook_id>/apply-template', TenantPlaybookApplyTemplateView.as_view()),
    path('tenant/playbook/<int:playbook_id>/clauses', ClausePolicyListView.as_view()),
    path('tenant/playbook/<int:playbook_id>/clauses/<int:clause_id>', ClausePolicyDetailView.as_view()),
    # TenantRule API
    path('tenant/rules', TenantRuleListView.as_view()),
    path('tenant/rules/alerts', TenantRuleAlertsView.as_view()),
    path('tenant/rules/<int:rule_id>', TenantRuleDetailView.as_view()),
    # ResponseTemplate API
    path('tenant/response-templates', ResponseTemplateListView.as_view()),
    path('tenant/response-templates/<int:template_id>', ResponseTemplateDetailView.as_view()),
    # ローカル開発用ファイル配信
    path('local-file', LocalFileView.as_view()),

    # Compliance API
    path('compliance/rescore', ComplianceRescoreView.as_view()),
    path('compliance/law-change-hook', LawChangeHookView.as_view()),
    path('compliance/score-summary', ComplianceScoreSummaryView.as_view()),

    # Laws & Regulations API
    path('setting/law/list', LawListView.as_view()),
    path('setting/law/upload', LawListView.as_view()),
    path('setting/law/file/<int:file_id>', LawFileDownloadView.as_view()),
    path('setting/law/file/<int:file_id>/delete', LawFileDeleteView.as_view()),
    path('setting/law/<int:law_id>', LawDetailView.as_view()),
    path('setting/law/<int:law_id>/reindex', LawReindexView.as_view()),
]
