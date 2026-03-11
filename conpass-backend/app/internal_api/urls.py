from django.urls import path

from internal_api.views.tasks.account_active_summary.views import InternalApiTasksAccountActiveSummaryDailyView, \
    InternalApiTasksAccountActiveSummaryMonthlyView
from internal_api.views.tasks.account_storage_summary.views import InternalApiTasksAccountStorageSummaryDailyView, \
    InternalApiTasksAccountStorageSummaryMonthlyView
from internal_api.views.tasks.account_management.views import InternalApiTasksActivateAccountView, \
    InternalApiTasksInvalidateAccountView
from internal_api.views.tasks.contract_management.views import InternalApiTasksExpireContractView, \
    InternalApiTasksContractBodySearchSaveView, InternalApiTasksSendContractRenewMailView
from internal_api.views.tasks.file_upload_management.views import InternalApiTasksCheckUploadResultView, \
    InternalApiTasksCleanFailedUploadsView

urlpatterns = [
    path('tasks/push-daily-account-storage-summary-job', InternalApiTasksAccountStorageSummaryDailyView.as_view()),
    path('tasks/push-daily-account-active-summary-job', InternalApiTasksAccountActiveSummaryDailyView.as_view()),
    path('tasks/push-monthly-account-storage-summary-job', InternalApiTasksAccountStorageSummaryMonthlyView.as_view()),
    path('tasks/push-monthly-account-active-summary-job', InternalApiTasksAccountActiveSummaryMonthlyView.as_view()),
    path('tasks/push-midnight-account-activate', InternalApiTasksActivateAccountView.as_view()),
    path('tasks/push-midnight-account-invalidate', InternalApiTasksInvalidateAccountView.as_view()),
    path('tasks/push-daily2-contract-expire', InternalApiTasksExpireContractView.as_view()),
    path('tasks/push-weekly-contract-body-search-save', InternalApiTasksContractBodySearchSaveView.as_view()),
    path('tasks/push-daily-send-contract-renew-mail', InternalApiTasksSendContractRenewMailView.as_view()),
    path('tasks/push-daily-check-upload-status-job', InternalApiTasksCheckUploadResultView.as_view()),
    path('tasks/push-daily-clean-failed-uploads-job', InternalApiTasksCleanFailedUploadsView.as_view()),
]
