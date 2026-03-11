#!/usr/bin/env python3
"""
ローカル開発用: MySQLの契約書データをQdrantにインデックスするスクリプト。

使い方:
    cd /Users/hayashi/Desktop/ConPass/conpass-agent-backend
    docker exec conpass-agent sh -c 'cd /app && uv run scripts/local_ingest.py'

    または特定IDのみ:
    docker exec conpass-agent sh -c 'cd /app && uv run scripts/local_ingest.py --contract-id 25'

前提:
    - .env ファイルに正しい設定が入っていること (EMBEDDING_PROVIDER=fastembed)
    - conpass-backend-db-1 コンテナが同一Dockerネットワーク上で起動していること
    - Qdrant が起動していること
"""
import argparse
import logging
import os
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

# プロジェクトルートをsys.pathに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# Contract classifier（import失敗時はルールベースにフォールバック）
try:
    from app.services.contract_classifier import classify_contract as _classify_contract
    _CLASSIFIER_AVAILABLE = True
except ImportError as _e:
    _CLASSIFIER_AVAILABLE = False
    logging.getLogger("local_ingest").warning(f"契約分類モジュールが利用不可: {_e}")

import pymysql
import pymysql.cursors

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("local_ingest")


# ============================================================
# DB接続設定
# ============================================================
DB_HOST = os.getenv("DB_HOST", "db")   # Docker内からはサービス名 "db"
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "conpass")
DB_PASS = os.getenv("DB_PASS", "secret")
DB_NAME = os.getenv("DB_NAME", "conpass")


def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        charset="utf8mb4",
    )


# ============================================================
# Qdrant設定
# ============================================================
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "conpass")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1024"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))


# ============================================================
# モデル・クライアントの初期化
# ============================================================
def get_embed_model():
    from llama_index.embeddings.fastembed import FastEmbedEmbedding
    return FastEmbedEmbedding(model_name=EMBEDDING_MODEL)


def get_sparse_model():
    from fastembed import SparseTextEmbedding
    return SparseTextEmbedding(model_name="Qdrant/bm25")


def get_qdrant_client():
    from qdrant_client import QdrantClient
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


# ============================================================
# テキスト処理
# ============================================================
def html_to_text(body_raw: str) -> str:
    """URLデコード + HTML→プレーンテキスト変換。"""
    from bs4 import BeautifulSoup
    decoded = unquote(body_raw)
    text = BeautifulSoup(decoded, "html.parser").get_text(separator=" ", strip=True)
    return unicodedata.normalize("NFKC", text).strip()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """テキストを重複ありでチャンク分割する。"""
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


# ============================================================
# データ取得
# ============================================================
def fetch_contracts(limit: Optional[int] = None, contract_id: Optional[int] = None) -> List[Dict]:
    """有効な契約書をMySQLから取得する。"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # related_contract タイトル解決用: 全契約書の name→id マッピングを構築
            cur.execute("""
                SELECT id, name FROM conpass_contract
                WHERE type = 1 AND status NOT IN (0, 10, 11, 20) AND is_garbage = 0
            """)
            name_to_id: Dict[str, int] = {row["name"]: row["id"] for row in cur.fetchall()}

            where_clause = "c.type = 1 AND c.status NOT IN (0, 10, 11, 20) AND c.is_garbage = 0"
            if contract_id:
                where_clause += f" AND c.id = {int(contract_id)}"
            limit_clause = f"LIMIT {int(limit)}" if limit else ""

            cur.execute(f"""
                SELECT c.id, c.name, c.directory_id,
                       d.id as dir_id, d.name as dir_name
                FROM conpass_contract c
                LEFT JOIN conpass_directory d ON c.directory_id = d.id
                WHERE {where_clause}
                ORDER BY c.id
                {limit_clause}
            """)
            contracts = cur.fetchall()

            result = []
            for c in contracts:
                # ContractBody取得（is_adopted=1優先、なければ最新）
                cur.execute("""
                    SELECT body FROM conpass_contractbody
                    WHERE contract_id = %s AND status = 1
                    ORDER BY is_adopted DESC, updated_at DESC
                    LIMIT 1
                """, (c["id"],))
                body_row = cur.fetchone()

                # メタデータ取得
                cur.execute("""
                    SELECT mk.label, m.value, m.date_value
                    FROM conpass_metadata m
                    JOIN conpass_metakey mk ON m.key_id = mk.id
                    WHERE m.contract_id = %s AND m.status = 1
                """, (c["id"],))
                meta_rows = cur.fetchall()
                metadata = {}
                for meta in meta_rows:
                    val = meta.get("value") or ""
                    if meta.get("date_value"):
                        val = str(meta["date_value"])
                    if val and meta.get("label"):
                        metadata[meta["label"]] = val

                # related_contract タイトル → ID 解決
                related_contract_id = None
                related_title = metadata.get("related_contract", "")
                if related_title and related_title in name_to_id:
                    related_contract_id = name_to_id[related_title]
                    logger.debug(
                        f"契約書 {c['id']}: related_contract '{related_title}' → ID {related_contract_id}"
                    )

                result.append({
                    "id": c["id"],
                    "name": c["name"],
                    "directory_id": c["dir_id"],
                    "body": body_row["body"] if body_row else None,
                    "metadata": metadata,
                    "related_contract_id": related_contract_id,
                })

        return result
    finally:
        conn.close()


# ============================================================
# Qdrantへの書き込み
# ============================================================
def upsert_contract(
    contract: Dict,
    embed_model,
    sparse_model,
    qdrant_client,
) -> int:
    """1件の契約書を処理してQdrantに書き込む。書き込んだノード数を返す。"""
    from qdrant_client.models import PointStruct, SparseVector, VectorParams
    import uuid

    contract_id = contract["id"]
    body_raw = contract.get("body")

    if not body_raw:
        logger.warning(f"契約書 {contract_id}: 本文なし - スキップ")
        return 0

    text = html_to_text(body_raw)
    if not text:
        logger.warning(f"契約書 {contract_id}: テキスト抽出結果が空 - スキップ")
        return 0

    chunks = chunk_text(text)
    logger.debug(f"契約書 {contract_id}: {len(chunks)}チャンクに分割")

    # 既存ポイントを削除（再インデックス時の重複防止）
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        qdrant_client.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector=Filter(
                must=[FieldCondition(key="contract_id", match=MatchValue(value=contract_id))]
            ),
        )
    except Exception as e:
        logger.warning(f"契約書 {contract_id}: 既存ポイント削除エラー: {e}")

    # ベースメタデータ
    base_meta = {
        "contract_id": contract_id,
        "name": contract.get("name", ""),
        "directory_id": contract.get("directory_id"),
    }
    # MetaKeyラベル→フィールド名マッピング（metadata_map.pyに準拠）
    label_map = {
        "title": "契約書名_title",
        "companya": "会社名_甲_company_a",
        "companyb": "会社名_乙_company_b",
        "companyc": "会社名_丙_company_c",
        "companyd": "会社名_丁_company_d",
        "contractdate": "契約日_contract_date",
        "contractstartdate": "契約開始日_contract_start_date",
        "contractenddate": "契約終了日_contract_end_date",
        "cancelnotice": "契約終了日_cancel_notice_date",
        "cort": "裁判所_court",
        "conpass_contract_type": "契約種別_contract_type",
    }
    for label, field in label_map.items():
        if label in contract["metadata"]:
            base_meta[field] = contract["metadata"][label]

    # 日付フィールドに epoch 秒を追加（Qdrant RangeCondition は float のみ有効）
    _date_labels = {"contractdate", "contractstartdate", "contractenddate", "cancelnotice"}
    for label in _date_labels:
        field = label_map.get(label)
        if field and field in base_meta:
            try:
                epoch = datetime.strptime(base_meta[field], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
                base_meta[field + "_epoch"] = epoch
            except (ValueError, TypeError):
                pass

    # 契約種別 3階層分類
    if _CLASSIFIER_AVAILABLE:
        try:
            existing_type = contract["metadata"].get("conpass_contract_type")
            classification = _classify_contract(
                name=contract.get("name", ""),
                text=text,
                existing_type=existing_type,
                use_llm=True,
            )
            base_meta.update(classification)
        except Exception as e:
            logger.warning(f"契約書 {contract_id}: 分類失敗: {e}")

    # 関連契約ID（タイトル文字列から解決済み）
    if contract.get("related_contract_id"):
        base_meta["related_contract_id"] = contract["related_contract_id"]

    # 埋め込み生成
    points = []
    for i, chunk in enumerate(chunks):
        chunk_meta = {**base_meta, "chunk_index": i, "total_chunks": len(chunks)}

        # Dense embedding
        dense_vec = embed_model.get_text_embedding(chunk)

        # Sparse embedding
        sparse_embeddings = list(sparse_model.embed([chunk]))
        sparse_emb = sparse_embeddings[0]
        sparse_indices = [int(idx) for idx in sparse_emb.indices]
        sparse_values = [float(val) for val in sparse_emb.values]

        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{contract_id}_{i}"))
        points.append(PointStruct(
            id=point_id,
            vector={
                "dense": dense_vec,
                "sparse": SparseVector(indices=sparse_indices, values=sparse_values),
            },
            payload={**chunk_meta, "text": chunk},
        ))

    if points:
        qdrant_client.upsert(collection_name=QDRANT_COLLECTION, points=points)
        logger.info(f"契約書 {contract_id} ({contract.get('name', '')}): {len(points)}ノード書き込み完了")

    return len(points)


# ============================================================
# Qdrantインデックス管理
# ============================================================
def ensure_payload_indexes(qdrant_client) -> None:
    """分類フィールド等のペイロードインデックスを確実に作成する。"""
    from qdrant_client.models import PayloadSchemaType
    new_indexes = [
        ("contract_category", PayloadSchemaType.KEYWORD),
        ("contract_type", PayloadSchemaType.KEYWORD),
        ("contract_subtype", PayloadSchemaType.KEYWORD),
        ("classification_method", PayloadSchemaType.KEYWORD),
        ("related_contract_id", PayloadSchemaType.INTEGER),
        # 日付 epoch フィールド（RangeCondition 用）
        ("契約日_contract_date_epoch", PayloadSchemaType.FLOAT),
        ("契約開始日_contract_start_date_epoch", PayloadSchemaType.FLOAT),
        ("契約終了日_contract_end_date_epoch", PayloadSchemaType.FLOAT),
        ("契約終了日_cancel_notice_date_epoch", PayloadSchemaType.FLOAT),
    ]
    for field_name, schema_type in new_indexes:
        try:
            qdrant_client.create_payload_index(
                collection_name=QDRANT_COLLECTION,
                field_name=field_name,
                field_schema=schema_type,
            )
            logger.info(f"ペイロードインデックス作成: {field_name}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.debug(f"インデックス既存スキップ: {field_name}")
            else:
                logger.warning(f"インデックス作成エラー {field_name}: {e}")


# ============================================================
# メイン
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="契約書データをQdrantにインデックスする")
    parser.add_argument("--limit", type=int, default=None, help="処理する契約書の上限数")
    parser.add_argument("--contract-id", type=int, default=None, help="特定の契約書IDのみ処理")
    args = parser.parse_args()

    logger.info(f"=== ローカルインジェクション開始 ===")
    logger.info(f"Embedding model: {EMBEDDING_MODEL}")
    logger.info(f"Qdrant collection: {QDRANT_COLLECTION}")

    # モデル・クライアント初期化
    logger.info("モデルを初期化中...")
    embed_model = get_embed_model()
    sparse_model = get_sparse_model()
    qdrant_client = get_qdrant_client()
    logger.info("モデル初期化完了")

    # 新フィールドのペイロードインデックスを確保
    logger.info("Qdrantペイロードインデックスを確認中...")
    ensure_payload_indexes(qdrant_client)

    # 契約書取得
    logger.info("契約書データをMySQLから取得中...")
    contracts = fetch_contracts(limit=args.limit, contract_id=args.contract_id)
    logger.info(f"{len(contracts)}件の契約書を取得しました")

    if not contracts:
        logger.warning("処理対象の契約書がありません")
        return

    # インデックス処理
    total_nodes = 0
    skipped = 0

    for contract in contracts:
        try:
            nodes = upsert_contract(contract, embed_model, sparse_model, qdrant_client)
            if nodes == 0:
                skipped += 1
            total_nodes += nodes
        except Exception as e:
            logger.error(f"契約書 {contract['id']} の処理中にエラー: {e}", exc_info=True)
            skipped += 1

    logger.info(f"\n=== インデックス完了 ===")
    logger.info(f"処理件数: {len(contracts) - skipped}/{len(contracts)}")
    logger.info(f"生成ノード数: {total_nodes}")
    logger.info(f"スキップ: {skipped}件")

    # Qdrant確認
    info = qdrant_client.get_collection(QDRANT_COLLECTION)
    logger.info(f"Qdrant: {QDRANT_COLLECTION} に {info.points_count} ポイントが存在します")


if __name__ == "__main__":
    main()
