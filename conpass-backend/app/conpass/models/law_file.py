from django.db import models
from conpass.models.law_document import LawDocument


class LawFile(models.Model):
    law       = models.ForeignKey(LawDocument, on_delete=models.CASCADE, related_name='law_files')
    file_path = models.CharField(max_length=500)   # ローカルファイルの絶対パス
    filename  = models.CharField(max_length=255)   # 元のファイル名
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'conpass_lawfile'
        ordering = ['created_at']
