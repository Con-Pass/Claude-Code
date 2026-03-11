import hashlib
import hmac
import json
from logging import getLogger
from typing import Optional

import requests
from django.conf import settings
from django.utils import timezone

from conpass.models.gmo_sign import GmoSign, GmoSignSigner

logger = getLogger(__name__)


class GmoSignService:
    """
    GMO Sign API連携サービス
    APIキーが設定されていない場合はモック動作する
    """

    def __init__(self):
        self.api_key = getattr(settings, 'GMO_SIGN_API_KEY', '')
        self.api_url = getattr(settings, 'GMO_SIGN_API_URL', '')
        self.webhook_secret = getattr(settings, 'GMO_SIGN_WEBHOOK_SECRET', '')

    @property
    def is_mock(self):
        return not self.api_key or not self.api_url

    def _get_headers(self):
        return {
            'Content-Type': 'application/json',
            'X-Api-Key': self.api_key,
        }

    def create_document(self, contract, file_data: bytes, filename: str,
                        signers: list, user=None) -> GmoSign:
        """
        電子契約文書を作成し、署名者を登録する。
        signers: [{'email': '...', 'name': '...', 'order': 1}, ...]
        """
        if self.is_mock:
            return self._mock_create_document(contract, signers, user)

        payload = {
            'document_name': contract.name,
            'file_name': filename,
        }
        response = requests.post(
            f'{self.api_url}/documents',
            headers=self._get_headers(),
            json=payload,
        )
        response.raise_for_status()
        result = response.json()

        gmo_sign = GmoSign.objects.create(
            contract=contract,
            gmo_document_id=result['document_id'],
            status='DRAFT',
            created_by=user,
        )

        for signer_data in signers:
            GmoSignSigner.objects.create(
                gmo_sign=gmo_sign,
                email=signer_data['email'],
                name=signer_data['name'],
                order=signer_data.get('order', 1),
            )

        return gmo_sign

    def send_for_signature(self, gmo_sign: GmoSign) -> GmoSign:
        """
        署名依頼を送信する。
        """
        if self.is_mock:
            return self._mock_send_for_signature(gmo_sign)

        signers_payload = []
        for signer in gmo_sign.signers.all():
            signers_payload.append({
                'email': signer.email,
                'name': signer.name,
                'order': signer.order,
            })

        payload = {
            'document_id': gmo_sign.gmo_document_id,
            'signers': signers_payload,
        }
        response = requests.post(
            f'{self.api_url}/documents/{gmo_sign.gmo_document_id}/send',
            headers=self._get_headers(),
            json=payload,
        )
        response.raise_for_status()

        gmo_sign.status = 'SENT'
        gmo_sign.sent_at = timezone.now()
        gmo_sign.save(update_fields=['status', 'sent_at', 'updated_at'])

        return gmo_sign

    def get_status(self, gmo_sign: GmoSign) -> dict:
        """
        文書のステータスを取得する。
        """
        if self.is_mock:
            return self._mock_get_status(gmo_sign)

        response = requests.get(
            f'{self.api_url}/documents/{gmo_sign.gmo_document_id}',
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def cancel(self, gmo_sign: GmoSign) -> GmoSign:
        """
        署名依頼をキャンセルする。
        """
        if self.is_mock:
            return self._mock_cancel(gmo_sign)

        response = requests.post(
            f'{self.api_url}/documents/{gmo_sign.gmo_document_id}/cancel',
            headers=self._get_headers(),
        )
        response.raise_for_status()

        gmo_sign.status = 'CANCELLED'
        gmo_sign.save(update_fields=['status', 'updated_at'])

        return gmo_sign

    def verify_webhook_signature(self, payload_body: bytes, signature: str) -> bool:
        """
        Webhookの署名を検証する。
        """
        if not self.webhook_secret:
            return True
        expected = hmac.HMAC(
            self.webhook_secret.encode('utf-8'),
            payload_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def handle_webhook_event(self, event_type: str, data: dict):
        """
        Webhookイベントを処理する。
        """
        document_id = data.get('document_id', '')

        try:
            gmo_sign = GmoSign.objects.get(gmo_document_id=document_id)
        except GmoSign.DoesNotExist:
            logger.warning(f"GmoSign not found for document_id: {document_id}")
            return

        if event_type == 'document.signed':
            self._handle_signed(gmo_sign, data)
        elif event_type == 'document.declined':
            self._handle_declined(gmo_sign, data)
        elif event_type == 'document.expired':
            self._handle_expired(gmo_sign)
        elif event_type == 'signer.completed':
            self._handle_signer_completed(gmo_sign, data)
        elif event_type == 'document.reminder':
            logger.info(f"Reminder event for document: {document_id}")

    def _handle_signed(self, gmo_sign: GmoSign, data: dict):
        """署名完了イベント処理"""
        gmo_sign.status = 'SIGNED'
        gmo_sign.signed_at = timezone.now()
        gmo_sign.save(update_fields=['status', 'signed_at', 'updated_at'])

        # Contract.statusも更新（署名完了）
        contract = gmo_sign.contract
        if hasattr(contract, 'Status') and hasattr(contract.Status, 'SIGNED'):
            contract.status = contract.Status.SIGNED.value
            contract.save(update_fields=['status'])

        logger.info(f"Document signed: {gmo_sign.gmo_document_id}")

    def _handle_declined(self, gmo_sign: GmoSign, data: dict):
        """署名拒否イベント処理"""
        gmo_sign.status = 'DECLINED'
        gmo_sign.save(update_fields=['status', 'updated_at'])

        signer_email = data.get('signer_email', '')
        if signer_email:
            gmo_sign.signers.filter(email=signer_email).update(
                status='DECLINED',
                updated_at=timezone.now(),
            )

        logger.info(f"Document declined: {gmo_sign.gmo_document_id} by {signer_email}")

    def _handle_expired(self, gmo_sign: GmoSign):
        """期限切れイベント処理"""
        gmo_sign.status = 'EXPIRED'
        gmo_sign.save(update_fields=['status', 'updated_at'])
        logger.info(f"Document expired: {gmo_sign.gmo_document_id}")

    def _handle_signer_completed(self, gmo_sign: GmoSign, data: dict):
        """個別署名者の署名完了"""
        signer_email = data.get('signer_email', '')
        if signer_email:
            gmo_sign.signers.filter(email=signer_email).update(
                status='SIGNED',
                signed_at=timezone.now(),
                updated_at=timezone.now(),
            )
        logger.info(f"Signer completed: {signer_email} for {gmo_sign.gmo_document_id}")

    # --- モック実装 ---

    def _mock_create_document(self, contract, signers, user) -> GmoSign:
        import uuid
        mock_document_id = f"mock_{uuid.uuid4().hex[:16]}"

        gmo_sign = GmoSign.objects.create(
            contract=contract,
            gmo_document_id=mock_document_id,
            status='DRAFT',
            created_by=user,
        )

        for signer_data in signers:
            GmoSignSigner.objects.create(
                gmo_sign=gmo_sign,
                email=signer_data['email'],
                name=signer_data['name'],
                order=signer_data.get('order', 1),
            )

        logger.info(f"[MOCK] Created document: {mock_document_id}")
        return gmo_sign

    def _mock_send_for_signature(self, gmo_sign: GmoSign) -> GmoSign:
        gmo_sign.status = 'SENT'
        gmo_sign.sent_at = timezone.now()
        gmo_sign.save(update_fields=['status', 'sent_at', 'updated_at'])
        logger.info(f"[MOCK] Sent for signature: {gmo_sign.gmo_document_id}")
        return gmo_sign

    def _mock_get_status(self, gmo_sign: GmoSign) -> dict:
        signers = []
        for s in gmo_sign.signers.all():
            signers.append({
                'email': s.email,
                'name': s.name,
                'order': s.order,
                'status': s.status,
            })
        return {
            'document_id': gmo_sign.gmo_document_id,
            'status': gmo_sign.status,
            'signers': signers,
        }

    def _mock_cancel(self, gmo_sign: GmoSign) -> GmoSign:
        gmo_sign.status = 'CANCELLED'
        gmo_sign.save(update_fields=['status', 'updated_at'])
        logger.info(f"[MOCK] Cancelled: {gmo_sign.gmo_document_id}")
        return gmo_sign
