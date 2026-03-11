"""
Google Document AI を用いた PDF テキスト抽出 Cloud Function

Gemini OCR（conpass-ocr-gemini）と同一インターフェース:
  入力: {"pdf_uri": "gs://bucket/path.pdf", "pdf_size": N}
  出力: {"ocr_results": "<html>...</html>"}

Gemini OCR との主な違い:
  - Document AI は LLM による生成ではなく光学的 OCR を実施するため hallucination がない
  - テーブル構造（別表・附表）を <table> タグとして保持
  - 縦位置ソートにより読み取り順序を保持

【GCP セットアップ】
1. Document AI API を有効化
   gcloud services enable documentai.googleapis.com --project=purple-conpass

2. Enterprise Document OCR プロセッサを作成
   https://console.cloud.google.com/ai/document-ai/processors
   → 「プロセッサを作成」→「Enterprise Document OCR」を選択
   → リージョン: us（またはプロジェクト設定に合わせて）
   → 作成後に表示されるプロセッサ ID をメモ

3. Cloud Function のデプロイ
   cd conpass-backend/functions/conpass-ocr-documentai
   gcloud functions deploy conpass-ocr-documentai-staging \\
     --gen2 \\
     --region=asia-northeast1 \\
     --runtime=python311 \\
     --trigger-http \\
     --allow-unauthenticated \\
     --set-env-vars DOCUMENTAI_PROCESSOR_ID=<プロセッサID> \\
     --timeout=540s \\
     --memory=512MB \\
     --entry-point=process_pdf

4. Django .env を更新
   GV_OCR_GEMINI_ENDPOINT=https://asia-northeast1-purple-conpass.cloudfunctions.net/conpass-ocr-documentai-staging
"""

import json
import os
import functions_framework
from google.cloud import documentai_v1 as documentai
from google.cloud import storage

PROJECT_ID   = os.environ.get("GCP_PROJECT_ID", "purple-conpass")
LOCATION     = os.environ.get("DOCUMENTAI_LOCATION", "us")
PROCESSOR_ID = os.environ.get("DOCUMENTAI_PROCESSOR_ID", "")

# 同期 API のページ数上限（Enterprise Document OCR は ~30 ページまで同期対応）
ONLINE_PAGE_LIMIT = 30


@functions_framework.http
def process_pdf(request):
    """
    メインエントリポイント。
    Gemini OCR と同一インターフェースで Document AI OCR を提供する。
    """
    try:
        data = request.get_json(silent=True) or {}
        pdf_uri  = data.get("pdf_uri", "")
        pdf_size = int(data.get("pdf_size", 0))

        if not pdf_uri:
            return json.dumps({"error": "pdf_uri is required"}), 400
        if not PROCESSOR_ID:
            return json.dumps({"error": "DOCUMENTAI_PROCESSOR_ID is not configured"}), 500

        print(f"[DocumentAI OCR] pdf_uri={pdf_uri} pdf_size={pdf_size}")

        if pdf_size > ONLINE_PAGE_LIMIT:
            # ページ数が多い場合はバッチ処理経由
            html = _process_batch(pdf_uri)
        else:
            html = _process_online(pdf_uri)

        return json.dumps({"ocr_results": html}, ensure_ascii=False), 200, {
            "Content-Type": "application/json; charset=utf-8"
        }

    except Exception as e:
        import traceback
        print(f"[DocumentAI OCR] Error: {e}")
        traceback.print_exc()
        return json.dumps({"error": str(e)}), 500


# ── オンライン処理（同期・~30ページ） ──────────────────────────────────────

def _process_online(pdf_uri: str) -> str:
    """Document AI オンライン API（同期）でテキストを抽出する"""
    client = documentai.DocumentProcessorServiceClient(
        client_options={"api_endpoint": f"{LOCATION}-documentai.googleapis.com"}
    )
    processor_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"

    # GCS URI を直接渡す（ダウンロード不要）
    gcs_document = documentai.GcsDocument(
        gcs_uri=pdf_uri,
        mime_type="application/pdf",
    )
    req = documentai.ProcessRequest(
        name=processor_name,
        gcs_document=gcs_document,
        skip_human_review=True,
    )

    result = client.process_document(request=req)
    print(f"[DocumentAI OCR] online: pages={len(result.document.pages)}")
    return _document_to_html(result.document)


# ── バッチ処理（非同期・31ページ以上） ────────────────────────────────────

def _process_batch(pdf_uri: str) -> str:
    """
    Document AI バッチ API を使用し、GCS に出力後に読み取って返す。
    大規模 PDF（> 30 ページ）向け。
    """
    import time
    from google.longrunning import operations_pb2

    client = documentai.DocumentProcessorServiceClient(
        client_options={"api_endpoint": f"{LOCATION}-documentai.googleapis.com"}
    )
    processor_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"

    # 出力先 GCS パス（一時ディレクトリ）
    output_bucket = "conpass-filedata-staging"
    output_prefix = f"documentai-output/{os.urandom(8).hex()}/"
    output_uri    = f"gs://{output_bucket}/{output_prefix}"

    req = documentai.BatchProcessRequest(
        name=processor_name,
        input_documents=documentai.BatchDocumentsInputConfig(
            gcs_documents=documentai.GcsDocuments(
                documents=[documentai.GcsDocument(gcs_uri=pdf_uri, mime_type="application/pdf")]
            )
        ),
        document_output_config=documentai.DocumentOutputConfig(
            gcs_output_config=documentai.DocumentOutputConfig.GcsOutputConfig(
                gcs_uri=output_uri
            )
        ),
    )

    operation = client.batch_process_documents(request=req)
    print(f"[DocumentAI OCR] batch started: operation={operation.operation.name}")

    # 最大 10 分ポーリング（Cloud Function gen2 timeout=540s）
    timeout = 480
    interval = 10
    elapsed  = 0
    while not operation.done() and elapsed < timeout:
        time.sleep(interval)
        elapsed += interval
        operation = client.get_operation(operation.operation)
        print(f"[DocumentAI OCR] waiting... {elapsed}s done={operation.done()}")

    if not operation.done():
        raise TimeoutError("Document AI batch processing timed out")

    # GCS から結果 JSON を取得
    storage_client = storage.Client()
    bucket = storage_client.bucket(output_bucket)
    blobs  = list(bucket.list_blobs(prefix=output_prefix))
    print(f"[DocumentAI OCR] batch output: {len(blobs)} files")

    full_html_parts = ["<html><body>"]
    for blob in sorted(blobs, key=lambda b: b.name):
        if not blob.name.endswith(".json"):
            continue
        doc_json = json.loads(blob.download_as_text())
        document = documentai.Document.from_json(json.dumps(doc_json))
        # ページ区切りを追加
        if len(full_html_parts) > 1:
            full_html_parts.append("<hr>")
        full_html_parts.append(_document_to_html(document, wrap_html=False))
        # 一時ファイルを削除
        blob.delete()

    full_html_parts.append("</body></html>")
    return "\n".join(full_html_parts)


# ── Document → HTML 変換 ───────────────────────────────────────────────────

def _layout_to_text(layout: "documentai.Document.Page.Layout", full_text: str) -> str:
    """テキストアンカーから実際のテキストを抽出する"""
    result = ""
    for seg in layout.text_anchor.text_segments:
        start = int(seg.start_index) if seg.start_index else 0
        end   = int(seg.end_index)
        result += full_text[start:end]
    return result.strip()


def _document_to_html(document: "documentai.Document", wrap_html: bool = True) -> str:
    """
    Document AI レスポンスを HTML に変換する。

    - 段落 → <p>
    - テーブル → <table><tr><td>（別表・附表の構造を保持）
    - ページ内の要素を縦位置（Y 座標）でソートして読み取り順を維持
    """
    full_text = document.text
    parts     = ["<html><body>"] if wrap_html else []

    for page_idx, page in enumerate(document.pages):
        if page_idx > 0:
            parts.append("<hr>")

        elements = []  # (y_pos, html_str)

        # 段落
        for para in page.paragraphs:
            text = _layout_to_text(para.layout, full_text)
            if not text:
                continue
            verts = para.layout.bounding_poly.normalized_vertices
            y     = verts[0].y if verts else 0.0
            elements.append((y, f"<p>{text}</p>"))

        # テーブル（別表・附表など）
        for table in page.tables:
            rows = []
            for row in table.header_rows:
                cells = [
                    f"<td><strong>{_layout_to_text(c.layout, full_text)}</strong></td>"
                    for c in row.cells
                ]
                rows.append("<tr>" + "".join(cells) + "</tr>")
            for row in table.body_rows:
                cells = [
                    f"<td>{_layout_to_text(c.layout, full_text)}</td>"
                    for c in row.cells
                ]
                rows.append("<tr>" + "".join(cells) + "</tr>")

            verts = table.layout.bounding_poly.normalized_vertices if hasattr(table, "layout") else []
            y     = verts[0].y if verts else 0.0
            table_html = "<table>" + "".join(rows) + "</table>"
            elements.append((y, table_html))

        # 縦位置でソート（読み取り順を維持）
        elements.sort(key=lambda x: x[0])
        for _, html_str in elements:
            parts.append(html_str)

    if wrap_html:
        parts.append("</body></html>")

    return "\n".join(parts)
