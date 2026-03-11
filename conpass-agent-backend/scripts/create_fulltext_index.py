"""
Qdrant の contracts コレクションに full-text index を作成するスクリプト。

text フィールドに MULTILINGUAL tokenizer の payload index を追加することで
MatchText フィルタによるキーワード検索が有効になる。

BM25 sparse 検索が日本語固有名詞を苦手とする問題を補完するために使用する。

Usage:
    docker exec conpass-agent /app/.venv/bin/python -m scripts.create_fulltext_index

Notes:
    - 一度作成すれば再実行しても既存インデックスはそのまま（冪等）
    - 既存ポイントにも自動的にインデックスが適用される（再インジェスト不要）
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from qdrant_client import QdrantClient
from qdrant_client.http import models

QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "conpass")


def create_fulltext_index() -> None:
    if not QDRANT_URL:
        print("ERROR: QDRANT_URL is not set", file=sys.stderr)
        sys.exit(1)

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=30.0)

    print(f"Connecting to Qdrant: {QDRANT_URL}")
    print(f"Collection: {QDRANT_COLLECTION}")

    # コレクション存在確認
    collections = client.get_collections().collections
    names = [c.name for c in collections]
    if QDRANT_COLLECTION not in names:
        print(f"ERROR: Collection '{QDRANT_COLLECTION}' not found. Available: {names}")
        sys.exit(1)

    # full-text index 作成（冪等: 既存でも成功する）
    client.create_payload_index(
        collection_name=QDRANT_COLLECTION,
        field_name="text",
        field_schema=models.TextIndexParams(
            type=models.TextIndexType.TEXT,
            tokenizer=models.TokenizerType.MULTILINGUAL,
            min_token_len=1,
            max_token_len=20,
            lowercase=True,
        ),
    )

    print("Full-text index created successfully on field 'text'")
    print("Tokenizer: MULTILINGUAL (CJK characters split per-character)")
    print("Existing points will be indexed automatically.")


if __name__ == "__main__":
    create_fulltext_index()
