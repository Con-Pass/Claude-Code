from django.db import models


class GmoSign(models.Model):
    """
    GMO Sign電子契約連携情報
    """

    STATUS_CHOICES = [
        ('DRAFT', '下書き'),
        ('SENT', '送信済み'),
        ('SIGNED', '署名完了'),
        ('DECLINED', '署名拒否'),
        ('EXPIRED', '期限切れ'),
        ('CANCELLED', 'キャンセル'),
    ]

    contract = models.ForeignKey('Contract', on_delete=models.CASCADE, related_name='gmo_signs')
    workflow = models.ForeignKey('Workflow', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='gmo_signs')
    gmo_document_id = models.CharField(max_length=512, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    sent_at = models.DateTimeField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='gmo_sign_created_by')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"GmoSign({self.gmo_document_id}) - {self.get_status_display()}"


class GmoSignSigner(models.Model):
    """
    GMO Sign署名者情報
    """

    STATUS_CHOICES = [
        ('PENDING', '署名待ち'),
        ('SIGNED', '署名済み'),
        ('DECLINED', '署名拒否'),
    ]

    gmo_sign = models.ForeignKey(GmoSign, on_delete=models.CASCADE, related_name='signers')
    email = models.EmailField()
    name = models.CharField(max_length=255)
    order = models.IntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    signed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.name} ({self.email})"
