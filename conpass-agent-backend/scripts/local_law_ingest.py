"""
ローカル開発用 法令手動インジェストスクリプト

使用例:
  uv run scripts/local_law_ingest.py --file /path/to/取適法.txt --law-name "取適法" --short-name "取適法"
  uv run scripts/local_law_ingest.py --text "第1条 この法律は..." --law-name "サンプル法"

環境変数 (または .env):
  QDRANT_URL, QDRANT_API_KEY, QDRANT_LAWS_COLLECTION, EMBEDDING_MODEL
"""
import argparse
import logging
import os
import re
import sys
import uuid

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("local_law_ingest")

# プロジェクトルートを PYTHONPATH に追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from qdrant_client import QdrantClient
from qdrant_client.models import (
    PointStruct, SparseVector, VectorParams, Distance, SparseVectorParams,
    Filter, FieldCondition, MatchValue, PayloadSchemaType,
)
from fastembed import TextEmbedding, SparseTextEmbedding

QDRANT_URL        = os.environ["QDRANT_URL"]
QDRANT_API_KEY    = os.environ.get("QDRANT_API_KEY", "")
LAWS_COLLECTION   = os.environ.get("QDRANT_LAWS_COLLECTION", "conpass_laws")
EMBEDDING_MODEL   = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

ARTICLE_PATTERN = re.compile(r'(?=第\d+条|Article\s+\d+)', re.IGNORECASE)


def get_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)


def ensure_collection(client: QdrantClient) -> None:
    try:
        client.get_collection(LAWS_COLLECTION)
        logger.info(f"コレクション {LAWS_COLLECTION} は既存")
        return
    except Exception:
        pass

    client.create_collection(
        collection_name=LAWS_COLLECTION,
        vectors_config={"dense": VectorParams(size=384, distance=Distance.COSINE)},
        sparse_vectors_config={"sparse": SparseVectorParams()},
    )
    for field, schema in [
        ("law_id",         PayloadSchemaType.INTEGER),
        ("law_name",       PayloadSchemaType.KEYWORD),
        ("law_short_name", PayloadSchemaType.KEYWORD),
        ("article_number", PayloadSchemaType.KEYWORD),
    ]:
        client.create_payload_index(LAWS_COLLECTION, field, schema)
    logger.info(f"コレクション {LAWS_COLLECTION} を作成しました")


def chunk_by_article(text: str, max_chars: int = 1500) -> list[str]:
    parts = ARTICLE_PATTERN.split(text)
    chunks = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) <= max_chars:
            chunks.append(part)
        else:
            for i in range(0, len(part), max_chars - 100):
                chunks.append(part[i:i + max_chars])
    return chunks or [text]


def extract_article_number(chunk: str) -> str:
    m = re.match(r'(第\d+条(?:の\d+)?|Article\s+\d+)', chunk)
    return m.group(1) if m else ""


def ingest(
    law_id: int,
    law_name: str,
    law_short_name: str,
    law_number: str,
    effective_date: str | None,
    text: str,
) -> int:
    client = get_client()
    ensure_collection(client)

    # 既存ポイントを削除
    try:
        client.delete(
            collection_name=LAWS_COLLECTION,
            points_selector=Filter(must=[FieldCondition(key="law_id", match=MatchValue(value=law_id))]),
        )
        logger.info(f"既存ポイントを削除: law_id={law_id}")
    except Exception:
        pass

    logger.info(f"Embedding モデルをロード中: {EMBEDDING_MODEL}")
    dense_model  = TextEmbedding(model_name=EMBEDDING_MODEL)
    sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")

    chunks = chunk_by_article(text)
    logger.info(f"チャンク数: {len(chunks)}")

    points = []
    for i, chunk in enumerate(chunks):
        article_number = extract_article_number(chunk)
        dense_vec   = list(dense_model.embed([chunk]))[0]
        sparse_emb  = list(sparse_model.embed([chunk]))[0]
        point_id    = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"law_{law_id}_{i}"))

        points.append(PointStruct(
            id=point_id,
            vector={
                "dense": list(dense_vec),
                "sparse": SparseVector(
                    indices=[int(x) for x in sparse_emb.indices],
                    values=[float(x) for x in sparse_emb.values],
                ),
            },
            payload={
                "law_id":         law_id,
                "law_name":       law_name,
                "law_short_name": law_short_name,
                "law_number":     law_number,
                "effective_date": effective_date,
                "article_number": article_number,
                "chunk_index":    i,
                "text":           chunk,
            },
        ))

    if points:
        client.upsert(collection_name=LAWS_COLLECTION, points=points)
        logger.info(f"Upsert 完了: {len(points)} ポイント → {LAWS_COLLECTION}")

    return len(points)


def main():
    parser = argparse.ArgumentParser(description="ローカル法令インジェスト")
    parser.add_argument("--law-id",    type=int,   default=1,  help="法令ID (デフォルト: 1)")
    parser.add_argument("--law-name",  required=True,          help="法令名")
    parser.add_argument("--short-name", default="",            help="略称")
    parser.add_argument("--law-number", default="",            help="法令番号")
    parser.add_argument("--effective-date", default=None,      help="施行日 (YYYY-MM-DD)")
    parser.add_argument("--file",       default=None,          help="法令テキストファイルパス")
    parser.add_argument("--text",       default=None,          help="法令テキスト（直接指定）")
    args = parser.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    elif args.text:
        text = args.text
    else:
        parser.error("--file または --text のいずれかを指定してください")

    count = ingest(
        law_id=args.law_id,
        law_name=args.law_name,
        law_short_name=args.short_name,
        law_number=args.law_number,
        effective_date=args.effective_date,
        text=text,
    )
    logger.info(f"完了: {args.law_name} → {count} 条文をインデックス化しました")


if __name__ == "__main__":
    main()
