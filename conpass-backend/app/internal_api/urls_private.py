from django.urls import path

from internal_api.views.tasks.account_active_summary.views import PrivateApiExecuteAccountActiveSummaryDailyView, \
    PrivateApiExecuteAccountActiveSummaryMonthlyView
from internal_api.views.tasks.account_storage_summary.views import PrivateApiExecuteAccountStorageSummaryDailyView, \
    PrivateApiExecuteAccountStorageSummaryMonthlyView
from internal_api.views.tasks.account_management.views import PrivateApiExecuteActiveAccountView, PrivateApiExecuteInvalidateAccountView
from internal_api.views.tasks.contract_management.views import PrivateApiExecuteExpireContractView, \
    PrivateApiExecuteContractBodySearchSaveView, PrivateApiExecuteSendC0jtractRenewMailView
from internal_api.views.tasks.file_upload_management.views import PrivateApiExecuteCheckUploadResultView, PrivateApiExecuteCleanFailedUploadsView
from internal_api.views.tasks.conpass.views import PrivateApiExecuteAdd, \
    PrivateApiExecuteVisionScanPdfTaskView, PrivateApiExecutePredictionTaskView
from internal_api.views.tasks.contract_upload_prediction_task.views import \
    PrivateApiExecutePredictionOnUploadTaskView, PrivateApiExecuteZipUploadTaskView, PrivateApiClassifyByQrcodePresenceTaskView

urlpatterns = [
    path('task/execute/add', PrivateApiExecuteAdd.as_view()),
    path('task/execute/vision-scan-pdf-task', PrivateApiExecuteVisionScanPdfTaskView.as_view()),
    path('task/execute/prediction-task', PrivateApiExecutePredictionTaskView.as_view()),
    path('task/execute/create-daily-account-active-summary', PrivateApiExecuteAccountActiveSummaryDailyView.as_view()),
    path('task/execute/create-monthly-account-active-summary', PrivateApiExecuteAccountActiveSummaryMonthlyView.as_view()),
    path('task/execute/activate-account', PrivateApiExecuteActiveAccountView.as_view()),
    path('task/execute/invalidate-account', PrivateApiExecuteInvalidateAccountView.as_view()),
    path('task/execute/create-daily-account-storage-summary', PrivateApiExecuteAccountStorageSummaryDailyView.as_view()),
    path('task/execute/create-monthly-account-storage-summary', PrivateApiExecuteAccountStorageSummaryMonthlyView.as_view()),
    path('task/execute/prediction-on-upload-task', PrivateApiExecutePredictionOnUploadTaskView.as_view()),
    path('task/execute/zip-upload-task', PrivateApiExecuteZipUploadTaskView.as_view()),
    path('task/execute/classify-by-qr-code-presence-task', PrivateApiClassifyByQrcodePresenceTaskView.as_view()),
    path('task/execute/expire-contract', PrivateApiExecuteExpireContractView.as_view()),
    path('task/execute/create-search-body-task', PrivateApiExecuteContractBodySearchSaveView.as_view()),
    path('task/execute/send-contract-renew-mail-task', PrivateApiExecuteSendC0jtractRenewMailView.as_view()),
    path('task/execute/check-upload-result', PrivateApiExecuteCheckUploadResultView.as_view()),
    path('task/execute/clean-failed-uploads', PrivateApiExecuteCleanFailedUploadsView.as_view()),
]
