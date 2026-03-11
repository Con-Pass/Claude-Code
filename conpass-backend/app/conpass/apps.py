from django.apps import AppConfig
from django.conf import settings


class ConpassConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'conpass'

    def ready(self):
        # 開発環境でGCS認証情報がない場合はローカルフォールバックを適用
        import os
        if os.environ.get('ENVIRONMENT') in ('development', 'local', None, ''):
            try:
                import conpass.services.gcp.vision_service_local_patch  # noqa
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f'Failed to apply VisionService patch: {e}')
