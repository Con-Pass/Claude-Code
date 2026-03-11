from django.db import models
from conpass.models.account import Account


class LawDocument(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', '処理待ち'
        INDEXED = 'INDEXED', 'インデックス済み'
        FAILED  = 'FAILED',  '失敗'

    account        = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='law_documents')
    law_name       = models.CharField(max_length=200)
    law_short_name = models.CharField(max_length=50, blank=True)
    law_number     = models.CharField(max_length=100, blank=True)
    effective_date = models.DateField(null=True, blank=True)
    text           = models.TextField()
    applicable_contract_types = models.JSONField(default=list, blank=True)
    search_keywords           = models.JSONField(default=list, blank=True)
    status         = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    article_count  = models.IntegerField(default=0)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'conpass_lawdocument'
        ordering = ['-created_at']
