"""
全契約書を Qdrant に再インジェストするスクリプト。

BGE-M3 に換装後、全件の Dense+Sparse ベクトルを再生成する。
contract_ingest.py の _fetch_contract_from_db / _upsert_contract_sync を再利用する。

Usage:
    docker exec conpass-agent /app/.venv/bin/python -m scripts.reingest_all
    docker exec conpass-agent /app/.venv/bin/python -m scripts.reingest_all --batch-size 10
    docker exec conpass-agent /app/.venv/bin/python -m scripts.reingest_all --dry-run

Notes:
    - EMBEDDING_PROVIDER=bge-m3 であること（.env で設定）
    - QDRANT_COLLECTION が新コレクション名を指していること
    - BGE-M3 モデルが未キャッシュの場合は初回に HuggingFace からダウンロード（~1.7GB）
"""
import argparse
import os
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import pymysql
import pymysql.cursors

_DB_HOST = os.getenv("DB_HOST", "db")
_DB_PORT = int(os.getenv("DB_PORT", "3306"))
_DB_USER = os.getenv("DB_USER", "conpass")
_DB_PASS = os.getenv("DB_PASS", os.getenv("DB_PASSWORD", "secret"))
_DB_NAME = os.getenv("DB_NAME", os.getenv("DB_DATABASE", "conpass"))

DEFAULT_BATCH_SIZE = int(os.getenv("REINGEST_BATCH_SIZE", "20"))


def get_all_contract_ids() -> list[int]:
    """MySQL から対象契約書の ID を全件取得する。"""
    conn = pymysql.connect(
        host=_DB_HOST, port=_DB_PORT,
        user=_DB_USER, password=_DB_PASS, database=_DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM conpass_contract WHERE type = 1 AND is_garbage = 0 ORDER BY id"
            )
            return [row["id"] for row in cur.fetchall()]
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="全契約書を Qdrant に再インジェスト")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"一度に処理する契約書数（デフォルト: {DEFAULT_BATCH_SIZE}）")
    parser.add_argument("--dry-run", action="store_true",
                        help="DB から ID を取得するだけで実際のインジェストは行わない")
    parser.add_argument("--start-from", type=int, default=0,
                        help="この contract_id 以降から再開する（中断再開用）")
    args = parser.parse_args()

    # モデル・DB 設定の確認
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "fastembed")
    qdrant_collection  = os.getenv("QDRANT_COLLECTION", "conpass")
    print(f"EMBEDDING_PROVIDER : {embedding_provider}")
    print(f"QDRANT_COLLECTION  : {qdrant_collection}")
    print(f"DB                 : {_DB_USER}@{_DB_HOST}:{_DB_PORT}/{_DB_NAME}")
    print()

    if embedding_provider != "bge-m3":
        print(f"WARNING: EMBEDDING_PROVIDER={embedding_provider} (bge-m3 を推奨)")

    # BGE-M3 モデルのロード（モデルキャッシュがなければダウンロード）
    if not args.dry_run:
        print("BGE-M3 モデルをロード中（初回は ~1.7GB ダウンロード）...")
        from app.core.model_settings import init_model_settings
        init_model_settings()
        print("BGE-M3 ロード完了")
        print()

        from llama_index.core.settings import Settings as LlamaSettings
        from app.services.chatbot.tools.semantic_search.sparse_query import get_sparse_embedding_model
        from app.api.internal.contract_ingest import _upsert_contract_sync, _fetch_contract_from_db, _get_qdrant_client

        embed_model  = LlamaSettings.embed_model
        sparse_model = get_sparse_embedding_model()
        qdrant_client = _get_qdrant_client()

    # 全契約書 ID 取得
    print("DB から契約書 ID を取得中...")
    all_ids = get_all_contract_ids()
    if args.start_from:
        all_ids = [cid for cid in all_ids if cid >= args.start_from]
    print(f"対象件数: {len(all_ids)} 件")
    print()

    if args.dry_run:
        print("[DRY RUN] 実際のインジェストはスキップします。")
        print(f"先頭10件の ID: {all_ids[:10]}")
        return

    # バッチ処理
    total_nodes = 0
    errors: list[dict] = []
    start_time = time.time()

    for batch_start in range(0, len(all_ids), args.batch_size):
        batch_ids = all_ids[batch_start:batch_start + args.batch_size]
        batch_num = batch_start // args.batch_size + 1
        total_batches = (len(all_ids) + args.batch_size - 1) // args.batch_size

        print(f"Batch {batch_num}/{total_batches}: contract_ids {batch_ids[0]}〜{batch_ids[-1]}")

        for cid in batch_ids:
            try:
                contract = _fetch_contract_from_db(cid)
                if not contract:
                    print(f"  [SKIP] contract_id={cid}: DB に見つかりません")
                    continue
                nodes = _upsert_contract_sync(contract, embed_model, sparse_model, qdrant_client)
                total_nodes += nodes
                print(f"  [OK] contract_id={cid}: {nodes} チャンク")
            except Exception as e:
                print(f"  [ERROR] contract_id={cid}: {e}")
                errors.append({"contract_id": cid, "error": str(e)})

        elapsed = time.time() - start_time
        rate = (batch_start + len(batch_ids)) / elapsed if elapsed > 0 else 0
        remaining = (len(all_ids) - batch_start - len(batch_ids)) / rate if rate > 0 else 0
        print(f"  進捗: {batch_start + len(batch_ids)}/{len(all_ids)} 件 "
              f"({rate:.1f} 件/秒, 残り約 {remaining/60:.1f} 分)")
        print()

    elapsed_total = time.time() - start_time
    print("=" * 50)
    print(f"完了: {total_nodes} チャンク書き込み")
    print(f"エラー: {len(errors)} 件")
    print(f"所要時間: {elapsed_total/60:.1f} 分")
    if errors:
        print("エラー詳細:")
        for err in errors:
            print(f"  contract_id={err['contract_id']}: {err['error']}")


if __name__ == "__main__":
    main()
