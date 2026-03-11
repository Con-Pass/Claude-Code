"""
ローカル開発用: /api/local-file でローカルファイルを配信するView
GCS署名付きURLの代替として使用
"""
import os
import mimetypes
from logging import getLogger

from django.http import FileResponse, Http404
from django.views import View

logger = getLogger(__name__)

UPLOAD_DIR = "/app/media/uploads"


class LocalFileView(View):
    """GCSの代わりにローカルのファイルを配信する（開発環境専用）"""

    def get(self, request):
        gcs_path = request.GET.get('path', '')
        if not gcs_path:
            raise Http404('path parameter required')

        # GCSパス(develop/1.pdf)をローカルファイル名(develop_1.pdf)に変換
        local_filename = gcs_path.replace('/', '_')
        local_path = os.path.join(UPLOAD_DIR, local_filename)

        if not os.path.exists(local_path):
            logger.warning(f'[LocalFileView] File not found: {local_path}')
            raise Http404(f'File not found: {gcs_path}')

        content_type, _ = mimetypes.guess_type(local_path)
        if content_type is None:
            content_type = 'application/octet-stream'

        logger.info(f'[LocalFileView] Serving: {local_path} ({content_type})')
        response = FileResponse(open(local_path, 'rb'), content_type=content_type)
        # PDFはインライン表示、その他はダウンロード
        if content_type == 'application/pdf':
            response['Content-Disposition'] = f'inline; filename="{os.path.basename(local_path)}"'
        else:
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(local_path)}"'
        return response
