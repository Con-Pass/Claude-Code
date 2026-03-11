"""
BGE-M3 用に Qdrant コレクションを再作成するスクリプト。

Dense: 1024次元 (BGE-M3)  ← 旧 384次元 (MiniLM)
Sparse: BGE-M3 SPLADE ベクトル（名前・フォーマットは互換）

処理フロー:
  1. 新コレクション <QDRANT_COLLECTION>_bge_m3 を作成
  2. 環境変数 QDRANT_COLLECTION をスワップして再インジェスト
  3. 旧コレクションを削除（任意）

Usage:
    docker exec conpass-agent /app/.venv/bin/python -m scripts.recreate_collection
    docker exec conpass-agent /app/.venv/bin/python -m scripts.recreate_collection --delete-old
"""
import argparse
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
    VectorsConfig,
)

QDRANT_URL        = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY    = os.getenv("QDRANT_API_KEY", "")
OLD_COLLECTION    = os.getenv("QDRANT_COLLECTION", "conpass")
NEW_COLLECTION    = os.getenv("QDRANT_COLLECTION_NEW", f"{OLD_COLLECTION}_bge_m3")


def create_bge_m3_collection(client: QdrantClient, name: str) -> None:
    """BGE-M3 用コレクションを作成する（既存ならスキップ）。"""
    existing = {c.name for c in client.get_collections().collections}
    if name in existing:
        print(f"コレクション '{name}' は既に存在します。スキップします。")
        return

    client.create_collection(
        collection_name=name,
        vectors_config={
            "dense": VectorParams(size=1024, distance=Distance.COSINE),
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False)),
        },
    )

    # Qdrant Cloud でのフィルタに必要な payload index を作成
    for field in ("contract_id", "directory_id"):
        client.create_payload_index(
            collection_name=name,
            field_name=field,
            field_schema=PayloadSchemaType.INTEGER,
        )
    client.create_payload_index(
        collection_name=name,
        field_name="private",
        field_schema=PayloadSchemaType.BOOL,
    )

    print(f"コレクション '{name}' を作成しました (dense=1024次元, sparse=BGE-M3 SPLADE)")


def delete_collection(client: QdrantClient, name: str) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if name not in existing:
        print(f"コレクション '{name}' は存在しません。スキップします。")
        return
    client.delete_collection(name)
    print(f"コレクション '{name}' を削除しました。")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--delete-old",
        action="store_true",
        help=f"旧コレクション '{OLD_COLLECTION}' を削除する",
    )
    args = parser.parse_args()

    if not QDRANT_URL:
        print("ERROR: QDRANT_URL が設定されていません。", file=sys.stderr)
        sys.exit(1)

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=30.0)

    print(f"Qdrant: {QDRANT_URL}")
    print(f"旧コレクション: {OLD_COLLECTION}")
    print(f"新コレクション: {NEW_COLLECTION}")
    print()

    create_bge_m3_collection(client, NEW_COLLECTION)

    print()
    print("次のステップ:")
    print(f"  1. .env の QDRANT_COLLECTION を '{NEW_COLLECTION}' に変更")
    print(f"  2. python -m scripts.reingest_all を実行して全件再インジェスト")
    print(f"  3. コンテナを再起動: docker-compose up -d --force-recreate conpass-agent")
    if not args.delete_old:
        print(f"  4. 動作確認後に旧コレクション削除:")
        print(f"     python -m scripts.recreate_collection --delete-old")
    else:
        print()
        delete_collection(client, OLD_COLLECTION)


if __name__ == "__main__":
    main()
