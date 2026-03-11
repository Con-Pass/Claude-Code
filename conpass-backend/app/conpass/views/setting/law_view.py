import io
import json
import logging
import mimetypes
import os
import uuid

import requests
from django.conf import settings
from django.http import FileResponse, Http404
from django.views import View
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.models.law_document import LawDocument
from conpass.models.law_file import LawFile

logger = logging.getLogger(__name__)

AGENT_INTERNAL_URL = getattr(settings, 'AGENT_INTERNAL_URL', 'http://conpass-agent:8080')
LAW_FILES_DIR = '/app/media/law_documents'


def _save_uploaded_file(uploaded_file) -> str:
    """アップロードされたファイルをローカルに保存し、パスを返す"""
    os.makedirs(LAW_FILES_DIR, exist_ok=True)
    ext = os.path.splitext(uploaded_file.name)[1]
    unique_name = f'{uuid.uuid4().hex}{ext}'
    dest_path = os.path.join(LAW_FILES_DIR, unique_name)
    with open(dest_path, 'wb') as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)
    return dest_path


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        import pdfminer.high_level
        return pdfminer.high_level.extract_text(io.BytesIO(file_bytes)).strip()
    except Exception as e:
        logger.error(f'[LawView] PDF text extraction failed: {e}')
        return ''


def _parse_json_list(value: str) -> list:
    """FormData から送られた JSON 配列文字列をパースして list[str] を返す。失敗時は空リスト。"""
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _file_info(f: LawFile) -> dict:
    """LawFileをJSON用dictに変換"""
    return {
        'id': f.id,
        'filename': f.filename,
        'url': f'/api/setting/law/file/{f.id}',
        'created_at': f.created_at,
    }


def _law_to_dict(law: LawDocument, include_text: bool = False) -> dict:
    """LawDocument を API レスポンス用 dict に変換"""
    d = {
        'id': law.id,
        'law_name': law.law_name,
        'law_short_name': law.law_short_name,
        'law_number': law.law_number,
        'effective_date': law.effective_date,
        'status': law.status,
        'article_count': law.article_count,
        'created_at': law.created_at,
        'applicable_contract_types': law.applicable_contract_types or [],
        'search_keywords': law.search_keywords or [],
        'files': [_file_info(f) for f in law.law_files.all()],
    }
    if include_text:
        d['text'] = law.text
    return d


def _build_ingest_payload(law: LawDocument, text: str) -> dict:
    """エージェントへの ingest リクエスト本体を生成"""
    return {
        'law_id': law.id,
        'law_name': law.law_name,
        'law_short_name': law.law_short_name,
        'law_number': law.law_number,
        'effective_date': str(law.effective_date) if law.effective_date else None,
        'text': text,
        'applicable_contract_types': law.applicable_contract_types or [],
        'search_keywords': law.search_keywords or [],
    }


class LawListView(APIView):
    """GET: 法令一覧  POST: 法令アップロード（複数ファイル対応）"""

    def get(self, request):
        laws = LawDocument.objects.filter(account=request.user.account).prefetch_related('law_files')
        return Response([_law_to_dict(law) for law in laws])

    def post(self, request):
        law_name       = request.data.get('law_name', '').strip()
        short_name     = request.data.get('law_short_name', '').strip()
        law_number     = request.data.get('law_number', '').strip()
        effective_date = request.data.get('effective_date') or None
        text           = request.data.get('text', '').strip()
        applicable_contract_types = _parse_json_list(request.data.get('applicable_contract_types', ''))
        search_keywords           = _parse_json_list(request.data.get('search_keywords', ''))

        # アップロードされたファイルからテキストを抽出（複数ファイル対応）
        uploaded_files = request.FILES.getlist('files') or (
            [request.FILES['file']] if 'file' in request.FILES else []
        )

        if uploaded_files and not text:
            parts = []
            for uf in uploaded_files:
                raw = uf.read()
                if uf.name.lower().endswith('.pdf') or uf.content_type == 'application/pdf':
                    parts.append(_extract_text_from_pdf(raw))
                else:
                    try:
                        parts.append(raw.decode('utf-8', errors='replace').strip())
                    except Exception:
                        pass
                uf.seek(0)  # 保存のために先頭に戻す
            text = '\n\n'.join(p for p in parts if p)

        if not law_name or not text:
            return Response({'detail': '法令名と本文（またはファイル）は必須です'}, status=400)

        law = LawDocument.objects.create(
            account=request.user.account,
            law_name=law_name,
            law_short_name=short_name,
            law_number=law_number,
            effective_date=effective_date,
            text=text,
            applicable_contract_types=applicable_contract_types,
            search_keywords=search_keywords,
            status=LawDocument.Status.PENDING,
        )

        # ファイルを LawFile として保存
        for uf in uploaded_files:
            path = _save_uploaded_file(uf)
            LawFile.objects.create(law=law, file_path=path, filename=uf.name)

        try:
            resp = requests.post(
                f'{AGENT_INTERNAL_URL}/api/internal/law/ingest',
                json=_build_ingest_payload(law, text),
                timeout=600,
            )
            resp.raise_for_status()
            result = resp.json()
            law.status = LawDocument.Status.INDEXED
            law.article_count = result.get('articles_indexed', 0)
        except Exception as e:
            logger.error(f'[LawIngest] failed for law_id={law.id}: {e}')
            law.status = LawDocument.Status.FAILED

        law.save()
        return Response({'id': law.id, 'status': law.status, 'article_count': law.article_count}, status=201)


class LawDetailView(APIView):
    """GET: 法令詳細（text含む）  PATCH: 法令メタ情報編集（ファイル追加含む）  DELETE: 法令削除"""

    def get(self, request, law_id):
        try:
            law = LawDocument.objects.prefetch_related('law_files').get(
                id=law_id, account=request.user.account
            )
        except LawDocument.DoesNotExist:
            return Response({'detail': '法令が見つかりません'}, status=404)
        return Response(_law_to_dict(law, include_text=True))

    def patch(self, request, law_id):
        try:
            law = LawDocument.objects.get(id=law_id, account=request.user.account)
        except LawDocument.DoesNotExist:
            return Response({'detail': '法令が見つかりません'}, status=404)

        if 'law_name' in request.data:
            law.law_name = request.data['law_name'].strip()
        if 'law_short_name' in request.data:
            law.law_short_name = request.data['law_short_name'].strip()
        if 'law_number' in request.data:
            law.law_number = request.data['law_number'].strip()
        if 'effective_date' in request.data:
            law.effective_date = request.data['effective_date'] or None
        if 'applicable_contract_types' in request.data:
            law.applicable_contract_types = _parse_json_list(request.data['applicable_contract_types'])
        if 'search_keywords' in request.data:
            law.search_keywords = _parse_json_list(request.data['search_keywords'])

        if not law.law_name:
            return Response({'detail': '法令名は必須です'}, status=400)

        # 追加ファイルの保存
        new_files = request.FILES.getlist('files') or (
            [request.FILES['file']] if 'file' in request.FILES else []
        )
        for uf in new_files:
            path = _save_uploaded_file(uf)
            LawFile.objects.create(law=law, file_path=path, filename=uf.name)

        # テキスト置換 → Qdrant 再インデックス
        new_text = request.data.get('text', '').strip()
        needs_reindex = bool(new_text)
        if new_text:
            law.text = new_text

        # applicable_contract_types / search_keywords が変更された場合も再インデックス
        if 'applicable_contract_types' in request.data or 'search_keywords' in request.data:
            needs_reindex = True

        law.save()

        if needs_reindex:
            try:
                requests.delete(f'{AGENT_INTERNAL_URL}/api/internal/law/{law.id}', timeout=30)
                resp = requests.post(
                    f'{AGENT_INTERNAL_URL}/api/internal/law/ingest',
                    json=_build_ingest_payload(law, law.text),
                    timeout=600,
                )
                resp.raise_for_status()
                law.article_count = resp.json().get('articles_indexed', 0)
                law.status = LawDocument.Status.INDEXED
                law.save(update_fields=['article_count', 'status'])
                logger.info(f'[LawEdit] reindexed law_id={law.id}: {law.article_count} articles')
            except Exception as e:
                logger.error(f'[LawEdit] reindex failed for law_id={law.id}: {e}')
                law.status = LawDocument.Status.FAILED
                law.save(update_fields=['status'])

        return Response(_law_to_dict(law))

    def delete(self, request, law_id):
        try:
            law = LawDocument.objects.get(id=law_id, account=request.user.account)
        except LawDocument.DoesNotExist:
            return Response({'detail': '法令が見つかりません'}, status=404)

        try:
            requests.delete(f'{AGENT_INTERNAL_URL}/api/internal/law/{law_id}', timeout=30)
        except Exception as e:
            logger.warning(f'[LawDelete] Qdrant cleanup failed for law_id={law_id}: {e}')

        law.delete()
        return Response(status=204)


class LawReindexView(APIView):
    """POST: 再インデックス"""

    def post(self, request, law_id):
        try:
            law = LawDocument.objects.get(id=law_id, account=request.user.account)
        except LawDocument.DoesNotExist:
            return Response({'detail': '法令が見つかりません'}, status=404)

        law.status = LawDocument.Status.PENDING
        law.save()

        try:
            requests.delete(f'{AGENT_INTERNAL_URL}/api/internal/law/{law_id}', timeout=30)
            resp = requests.post(
                f'{AGENT_INTERNAL_URL}/api/internal/law/ingest',
                json=_build_ingest_payload(law, law.text),
                timeout=600,
            )
            resp.raise_for_status()
            law.article_count = resp.json().get('articles_indexed', 0)
            law.status = LawDocument.Status.INDEXED
        except Exception as e:
            logger.error(f'[LawReindex] failed for law_id={law_id}: {e}')
            law.status = LawDocument.Status.FAILED

        law.save()
        return Response({'status': law.status, 'article_count': law.article_count})


class LawFileDeleteView(APIView):
    """DELETE: 法令ファイルを削除"""

    def delete(self, request, file_id):
        try:
            lf = LawFile.objects.select_related('law').get(
                id=file_id, law__account=request.user.account
            )
        except LawFile.DoesNotExist:
            return Response({'detail': 'ファイルが見つかりません'}, status=404)

        # ストレージからも削除
        if lf.file_path and os.path.exists(lf.file_path):
            try:
                os.remove(lf.file_path)
            except Exception:
                pass
        lf.delete()
        return Response(status=204)


class LawFileDownloadView(View):
    """GET: 法令ファイルをダウンロード/プレビュー（認証なしで一時アクセス可）"""

    def get(self, request, file_id):
        try:
            lf = LawFile.objects.get(id=file_id)
        except LawFile.DoesNotExist:
            raise Http404('File not found')

        if not lf.file_path or not os.path.exists(lf.file_path):
            raise Http404('File not found on disk')

        content_type, _ = mimetypes.guess_type(lf.filename)
        if content_type is None:
            content_type = 'application/octet-stream'

        response = FileResponse(open(lf.file_path, 'rb'), content_type=content_type)
        if content_type == 'application/pdf':
            response['Content-Disposition'] = f'inline; filename="{lf.filename}"'
        else:
            response['Content-Disposition'] = f'attachment; filename="{lf.filename}"'
        return response
