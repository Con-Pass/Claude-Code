"""
契約書 Webhook 内部エンドポイント

Django バックエンドからのみ呼び出される内部 API。
JWTAuthMiddleware はこのパス(/api/internal/*)をスキップする。

Django の notify_to_AI_agent Celery タスクが呼び出す:
  POST /api/internal/contract/webhook
  Header: x-api-key: <AI_AGENT_WEBHOOK_API_KEY>
  Body: {"contract_ids": [1, 2, 3], "event_type": "created|updated|deleted"}
"""
import asyncio
import logging
import os
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import unquote

import pymysql
import pymysql.cursors
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    SparseVector,
)

from app.core.config import settings
from app.core.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)

# DB接続設定（local_ingest.py と同じ環境変数名）
_DB_HOST = os.getenv("DB_HOST", "db")
_DB_PORT = int(os.getenv("DB_PORT", "3306"))
_DB_USER = os.getenv("DB_USER", "conpass")
_DB_PASS = os.getenv("DB_PASS", os.getenv("DB_PASSWORD", "secret"))
_DB_NAME = os.getenv("DB_NAME", os.getenv("DB_DATABASE", "conpass"))

_WEBHOOK_API_KEY = os.getenv("AI_AGENT_WEBHOOK_API_KEY", "")

_CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE", "1024"))
_CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))


class WebhookRequest(BaseModel):
    contract_ids: List[int]
    event_type: str  # "created" | "updated" | "deleted"


def _get_db_connection():
    return pymysql.connect(
        host=_DB_HOST,
        port=_DB_PORT,
        user=_DB_USER,
        password=_DB_PASS,
        database=_DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        charset="utf8mb4",
        connect_timeout=10,
    )


def _get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY, timeout=60)


def _tables_to_markdown(html_body: str) -> str:
    """HTML 内の <table> を Markdown テーブル形式に変換する。"""
    from bs4 import BeautifulSoup, NavigableString
    soup = BeautifulSoup(html_body, "html.parser")
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            table.decompose()
            continue
        md_rows = []
        is_first = True
        for row in rows:
            cells = row.find_all(["th", "td"])
            cell_texts = [
                c.get_text(separator=" ", strip=True).replace("|", "｜")
                for c in cells
            ]
            if not cell_texts:
                continue
            md_rows.append("| " + " | ".join(cell_texts) + " |")
            if is_first:
                md_rows.append("| " + " | ".join(["---"] * len(cell_texts)) + " |")
                is_first = False
        table.replace_with(NavigableString("\n" + "\n".join(md_rows) + "\n"))
    return str(soup)


def _html_to_text(body_raw: str) -> str:
    """URLデコード + HTML → プレーンテキスト変換（<table>はMarkdownに変換）"""
    from bs4 import BeautifulSoup
    decoded = unquote(body_raw)
    decoded = _tables_to_markdown(decoded)
    text = BeautifulSoup(decoded, "html.parser").get_text(separator=" ", strip=True)
    return unicodedata.normalize("NFKC", text).strip()


# 日付フィールド（epoch 変換対象）
_DATE_LABELS = {"contractdate", "contractstartdate", "contractenddate"}


def _date_to_epoch(date_str: str) -> Optional[float]:
    """ISO日付文字列 (YYYY-MM-DD) を Unix epoch 秒 (float) に変換。失敗時は None。"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
    except (ValueError, TypeError):
        return None


def _chunk_text(text: str) -> List[str]:
    """テキストをチャンク分割"""
    if len(text) <= _CHUNK_SIZE:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + _CHUNK_SIZE
        chunks.append(text[start:end])
        start += _CHUNK_SIZE - _CHUNK_OVERLAP
    return chunks


def _fetch_contract_from_db(contract_id: int) -> Optional[dict]:
    """MySQL から1件の契約書データを取得する（同期）"""
    conn = _get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id, c.name, c.directory_id
                FROM conpass_contract c
                WHERE c.id = %s AND c.type = 1 AND c.is_garbage = 0
                """,
                (contract_id,),
            )
            row = cur.fetchone()
            if not row:
                return None

            # ContractBody 取得（is_adopted=1 優先、なければ最新）
            cur.execute(
                """
                SELECT body FROM conpass_contractbody
                WHERE contract_id = %s AND status = 1
                ORDER BY is_adopted DESC, updated_at DESC
                LIMIT 1
                """,
                (contract_id,),
            )
            body_row = cur.fetchone()

            # メタデータ取得（古い順に取得し、有効な値を優先する）
            cur.execute(
                """
                SELECT mk.label, m.value, m.date_value
                FROM conpass_metadata m
                JOIN conpass_metakey mk ON m.key_id = mk.id
                WHERE m.contract_id = %s AND m.status = 1
                ORDER BY m.updated_at ASC
                """,
                (contract_id,),
            )
            meta_rows = cur.fetchall()
            # OCR失敗時のプレースホルダー値。同一ラベルに有効な値がある場合は使わない
            _PLACEHOLDER_VALUES = {"（テキスト抽出なし）", "不明"}
            metadata = {}
            for meta in meta_rows:
                val = meta.get("value") or ""
                if meta.get("date_value"):
                    val = str(meta["date_value"])
                label = meta.get("label")
                if not val or not label:
                    continue
                if val in _PLACEHOLDER_VALUES:
                    # 既に有効な値がある場合はプレースホルダーで上書きしない
                    if label not in metadata:
                        metadata[label] = val
                else:
                    metadata[label] = val

            return {
                "id":           row["id"],
                "name":         row["name"],
                "directory_id": row["directory_id"],
                "body":         body_row["body"] if body_row else None,
                "metadata":     metadata,
            }
    finally:
        conn.close()


def _upsert_contract_sync(
    contract: dict,
    embed_model,
    sparse_model,
    qdrant_client: QdrantClient,
) -> int:
    """契約書を Qdrant へ書き込む（同期関数。run_in_executor 内で呼ぶ）"""
    contract_id = contract["id"]
    body_raw = contract.get("body")

    if not body_raw:
        logger.warning(f"[ContractWebhook] 契約書 {contract_id}: ContractBody なし - スキップ")
        return 0

    text = _html_to_text(body_raw)
    if not text:
        logger.warning(f"[ContractWebhook] 契約書 {contract_id}: テキスト空 - スキップ")
        return 0

    chunks = _chunk_text(text)

    # 既存ポイントを削除（再インデックス時の重複防止）
    try:
        qdrant_client.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=Filter(must=[
                FieldCondition(key="contract_id", match=MatchValue(value=contract_id))
            ]),
        )
    except Exception as e:
        logger.warning(f"[ContractWebhook] 既存ポイント削除エラー cid={contract_id}: {e}")

    # ベースメタデータ（local_ingest.py の label_map と同じ）
    label_map = {
        "title":              "契約書名_title",
        "companya":           "会社名_甲_company_a",
        "companyb":           "会社名_乙_company_b",
        "contractdate":       "契約日_contract_date",
        "contractstartdate":  "契約開始日_contract_start_date",
        "contractenddate":    "契約終了日_contract_end_date",
        "conpass_contract_type": "契約種別_contract_type",
    }
    base_meta: dict = {
        "contract_id":  contract_id,
        "name":         contract.get("name", ""),
        "directory_id": contract.get("directory_id"),
    }
    for label, field in label_map.items():
        if label in contract.get("metadata", {}):
            base_meta[field] = contract["metadata"][label]

    # 日付フィールドに epoch 秒を追加（Qdrant RangeCondition は float のみ有効）
    for label in _DATE_LABELS:
        field = label_map.get(label)
        if field and field in base_meta:
            epoch = _date_to_epoch(base_meta[field])
            if epoch is not None:
                base_meta[field + "_epoch"] = epoch

    # 埋め込み生成 + Upsert
    # BGE-M3 の場合はバッチで Dense+Sparse を一括生成（1回の forward pass で効率化）
    points = []
    use_bge_m3 = settings.EMBEDDING_PROVIDER == "bge-m3"

    if use_bge_m3:
        from app.services.bge_m3 import encode_texts
        result = encode_texts(chunks, return_dense=True, return_sparse=True)
        dense_vecs     = result["dense_vecs"]       # np.ndarray (n, 1024)
        sparse_weights = result["lexical_weights"]  # list[dict[int, float]]

        for i, chunk in enumerate(chunks):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{contract_id}_{i}"))
            weights  = sparse_weights[i]
            points.append(PointStruct(
                id=point_id,
                vector={
                    "dense": dense_vecs[i].tolist(),
                    "sparse": SparseVector(
                        indices=[int(k) for k in weights.keys()],
                        values=[float(v) for v in weights.values()],
                    ),
                },
                payload={**base_meta, "chunk_index": i, "total_chunks": len(chunks), "text": chunk},
            ))
    else:
        for i, chunk in enumerate(chunks):
            dense_vec  = embed_model.get_text_embedding(chunk)
            sparse_emb = list(sparse_model.embed([chunk]))[0]

            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{contract_id}_{i}"))
            points.append(PointStruct(
                id=point_id,
                vector={
                    "dense": list(dense_vec),
                    "sparse": SparseVector(
                        indices=[int(x) for x in sparse_emb.indices],
                        values=[float(x) for x in sparse_emb.values],
                    ),
                },
                payload={**base_meta, "chunk_index": i, "total_chunks": len(chunks), "text": chunk},
            ))

    if points:
        qdrant_client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)

    logger.info(
        f"[ContractWebhook] 契約書 {contract_id} ({contract.get('name', '')}): "
        f"{len(points)} ノード書き込み完了"
    )
    return len(points)


@router.post("/webhook")
async def contract_webhook(
    req: WebhookRequest,
    x_api_key: str = Header(default=""),
):
    """
    Django の notify_to_AI_agent から呼ばれる内部 Webhook。
    契約書を Qdrant にインデックス（または削除）する。
    """
    # API キー検証（設定されている場合のみ）
    if _WEBHOOK_API_KEY and x_api_key != _WEBHOOK_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    logger.info(f"[ContractWebhook] event={req.event_type} contract_ids={req.contract_ids}")

    event_type = req.event_type.lower()
    contract_ids = req.contract_ids
    loop = asyncio.get_running_loop()

    # ── 削除イベント ──────────────────────────────────────────────────────────
    if event_type == "deleted":
        def _delete_all():
            client = _get_qdrant_client()
            deleted = 0
            for cid in contract_ids:
                try:
                    client.delete(
                        collection_name=settings.QDRANT_COLLECTION,
                        points_selector=Filter(must=[
                            FieldCondition(key="contract_id", match=MatchValue(value=cid))
                        ]),
                    )
                    logger.info(f"[ContractWebhook] Qdrant 削除完了 cid={cid}")
                    deleted += 1
                except Exception as e:
                    logger.warning(f"[ContractWebhook] Qdrant 削除エラー cid={cid}: {e}")
            return deleted

        deleted = await loop.run_in_executor(None, _delete_all)
        return {"deleted": deleted}

    # ── created / updated: インデックス処理 ──────────────────────────────────
    from llama_index.core.settings import Settings as LlamaSettings
    from app.services.chatbot.tools.semantic_search.sparse_query import get_sparse_embedding_model

    embed_model  = LlamaSettings.embed_model
    sparse_model = get_sparse_embedding_model()
    qdrant_client = _get_qdrant_client()

    total_nodes = 0
    errors: list = []

    for cid in contract_ids:
        try:
            # DB から取得（同期処理を executor へ）
            contract = await loop.run_in_executor(None, _fetch_contract_from_db, cid)
            if not contract:
                logger.warning(f"[ContractWebhook] 契約書 {cid} が DB に見つかりません")
                continue

            # Embedding + Upsert（同期処理を executor へ）
            nodes = await loop.run_in_executor(
                None,
                _upsert_contract_sync,
                contract, embed_model, sparse_model, qdrant_client,
            )
            total_nodes += nodes

        except Exception as e:
            logger.error(f"[ContractWebhook] 契約書 {cid} の処理エラー: {e}", exc_info=True)
            errors.append({"contract_id": cid, "error": str(e)})

    return {
        "indexed":        total_nodes,
        "contract_count": len(contract_ids),
        "errors":         errors,
    }
