#!/usr/bin/env python3
"""
既存 Qdrant ポイントに日付 epoch フィールドを追加するパッチスクリプト。

ベクトルの再計算は行わず、set_payload のみで既存ポイントを更新する（高速）。

使い方:
    docker exec conpass-agent sh -c 'cd /app && uv run scripts/add_epoch_fields.py'
    docker exec conpass-agent sh -c 'cd /app && uv run scripts/add_epoch_fields.py --dry-run'
"""
import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("add_epoch_fields")

QDRANT_URL        = os.getenv("QDRANT_URL")
QDRANT_API_KEY    = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "conpass")

# epoch 変換対象フィールド: Qdrant ペイロードキー → epoch キー
DATE_FIELDS = {
    "契約日_contract_date":           "契約日_contract_date_epoch",
    "契約開始日_contract_start_date": "契約開始日_contract_start_date_epoch",
    "契約終了日_contract_end_date":   "契約終了日_contract_end_date_epoch",
    "契約終了日_cancel_notice_date":  "契約終了日_cancel_notice_date_epoch",
}

SCROLL_BATCH = 200  # 1回のスクロールで取得する件数


def _iso_to_epoch(date_str: str) -> Optional[float]:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
    except (ValueError, TypeError):
        return None


def ensure_float_indexes(client) -> None:
    """epoch フィールドのペイロードインデックスを作成（既存なら無視）。"""
    from qdrant_client.models import PayloadSchemaType
    for epoch_field in DATE_FIELDS.values():
        try:
            client.create_payload_index(
                collection_name=QDRANT_COLLECTION,
                field_name=epoch_field,
                field_schema=PayloadSchemaType.FLOAT,
            )
            logger.info(f"インデックス作成: {epoch_field}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.debug(f"インデックス既存スキップ: {epoch_field}")
            else:
                logger.warning(f"インデックス作成エラー {epoch_field}: {e}")


def patch_all(dry_run: bool = False) -> None:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)

    if not dry_run:
        ensure_float_indexes(client)

    updated_points = 0
    skipped_points = 0
    offset = None

    logger.info(f"コレクション '{QDRANT_COLLECTION}' をスキャン中...")

    while True:
        # ページングで全ポイントを取得
        result, next_offset = client.scroll(
            collection_name=QDRANT_COLLECTION,
            offset=offset,
            limit=SCROLL_BATCH,
            with_payload=True,
            with_vectors=False,
        )

        if not result:
            break

        for point in result:
            payload = point.payload or {}
            epoch_updates = {}

            for date_field, epoch_field in DATE_FIELDS.items():
                date_val = payload.get(date_field)
                if date_val and epoch_field not in payload:
                    epoch = _iso_to_epoch(str(date_val))
                    if epoch is not None:
                        epoch_updates[epoch_field] = epoch

            if epoch_updates:
                if dry_run:
                    logger.info(f"[DRY-RUN] point_id={point.id} updates={epoch_updates}")
                else:
                    client.set_payload(
                        collection_name=QDRANT_COLLECTION,
                        payload=epoch_updates,
                        points=[point.id],
                    )
                updated_points += 1
            else:
                skipped_points += 1

        logger.info(
            f"スキャン進捗: 更新={updated_points}, スキップ={skipped_points} "
            f"(offset={next_offset})"
        )

        if next_offset is None:
            break
        offset = next_offset

    logger.info(
        f"\n=== パッチ完了 ===\n"
        f"更新ポイント数: {updated_points}\n"
        f"スキップ(変換不要/既適用): {skipped_points}"
    )


def main():
    parser = argparse.ArgumentParser(description="Qdrant ポイントに epoch フィールドを追加")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="実際に書き込まず更新対象を表示するだけ",
    )
    args = parser.parse_args()

    if args.dry_run:
        logger.info("=== DRY-RUN モード（書き込みなし）===")

    patch_all(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
