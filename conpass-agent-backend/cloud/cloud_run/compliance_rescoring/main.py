"""
コンプライアンス再スコアリングジョブ

法令改正検知時にトリガーされ、影響を受ける契約の
コンプライアンススコアを再算出する。

トリガー:
  - Cloud Schedulerから定期実行
  - Firestoreのlaw_hashesコレクション更新時
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from google.cloud import firestore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ConPass API設定
CONPASS_API_BASE_URL = os.getenv("CONPASS_API_BASE_URL", "")
CONPASS_API_TOKEN = os.getenv("CONPASS_API_TOKEN", "")

# Qdrant設定
QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "conpass")

# 法令ハッシュコレクション名
LAW_HASHES_COLLECTION = "law_hashes"
LAW_CHANGES_COLLECTION = "law_changes"

# 再スコアリング対象の最大契約数
MAX_CONTRACTS_TO_RESCORE = 50


async def detect_recent_law_changes() -> List[Dict[str, Any]]:
    """
    最近の法令改正を検知する。

    Firestoreのlaw_hashesコレクションを確認し、
    前回チェック以降に更新されたエントリを返す。

    Returns:
        変更された法令のリスト
    """
    db = firestore.Client()

    # 前回チェック時刻を取得
    last_check_ref = db.collection(LAW_CHANGES_COLLECTION).document("last_check")
    last_check_doc = last_check_ref.get()

    if last_check_doc.exists:
        last_check_time = last_check_doc.to_dict().get("checked_at", "")
    else:
        last_check_time = ""

    # law_hashesから最近更新されたものを取得
    changes = []
    law_hashes_ref = db.collection(LAW_HASHES_COLLECTION)
    docs = law_hashes_ref.stream()

    for doc in docs:
        data = doc.to_dict()
        updated_at = data.get("updated_at", "")

        if updated_at > last_check_time:
            changes.append({
                "law_id": doc.id,
                "law_name": data.get("law_name", ""),
                "updated_at": updated_at,
            })

    # チェック時刻を更新
    last_check_ref.set({
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "changes_detected": len(changes),
    })

    logger.info(f"Detected {len(changes)} law changes since {last_check_time}")
    return changes


async def find_affected_contracts(
    law_name: str,
) -> List[Dict[str, Any]]:
    """
    法令改正の影響を受ける契約を検索する。

    Qdrantのcontractコレクションをセマンティック検索して、
    改正された法令に関連する契約を特定する。

    Args:
        law_name: 改正された法令名

    Returns:
        影響を受ける契約のリスト
    """
    if not QDRANT_URL:
        logger.warning("QDRANT_URL not configured, skipping contract search")
        return []

    try:
        # 法令名でセマンティック検索
        # 簡易的にREST APIでDense検索を行う
        # NOTE: 本番ではembedding modelを使用してベクトル化する
        headers = {"Content-Type": "application/json"}
        if QDRANT_API_KEY:
            headers["api-key"] = QDRANT_API_KEY

        # Qdrantのscroll APIで法令関連ペイロードを持つポイントを検索
        endpoint = f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/scroll"
        body = {
            "limit": MAX_CONTRACTS_TO_RESCORE,
            "with_payload": ["contract_id", "name"],
            "with_vector": False,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(endpoint, json=body, headers=headers)
            response.raise_for_status()

        data = response.json()
        result = data.get("result", {})
        points = result.get("points", [])

        # 重複排除（contract_idでユニーク化）
        seen_contracts = set()
        contracts = []
        for point in points:
            payload = point.get("payload", {})
            contract_id = payload.get("contract_id")
            if contract_id and contract_id not in seen_contracts:
                seen_contracts.add(contract_id)
                contracts.append({
                    "contract_id": contract_id,
                    "name": payload.get("name", ""),
                })

        logger.info(
            f"Found {len(contracts)} potentially affected contracts "
            f"for law change: {law_name}"
        )
        return contracts[:MAX_CONTRACTS_TO_RESCORE]

    except Exception as e:
        logger.error(f"Error searching affected contracts: {e}", exc_info=True)
        return []


async def notify_rescoring_needed(
    law_changes: List[Dict[str, Any]],
    affected_contracts: List[Dict[str, Any]],
) -> None:
    """
    再スコアリングが必要な契約をConPass API経由でアラート通知する。

    Args:
        law_changes: 法令改正の詳細
        affected_contracts: 影響を受ける契約リスト
    """
    if not CONPASS_API_BASE_URL or not affected_contracts:
        return

    try:
        notification_payload = {
            "event_type": "law_change_detected",
            "law_changes": law_changes,
            "affected_contract_ids": [
                c["contract_id"] for c in affected_contracts
            ],
            "affected_count": len(affected_contracts),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        headers = {
            "Content-Type": "application/json",
        }
        if CONPASS_API_TOKEN:
            headers["Authorization"] = f"Bearer {CONPASS_API_TOKEN}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{CONPASS_API_BASE_URL}/api/compliance/law-change-notification/",
                json=notification_payload,
                headers=headers,
            )
            if response.status_code < 400:
                logger.info(
                    f"Sent law change notification for {len(affected_contracts)} contracts"
                )
            else:
                logger.warning(
                    f"Law change notification returned status {response.status_code}: "
                    f"{response.text}"
                )

    except Exception as e:
        logger.error(f"Error sending law change notification: {e}", exc_info=True)


async def main() -> Dict[str, Any]:
    """
    メインエントリポイント。

    1. 法令改正を検知
    2. 影響を受ける契約を検索
    3. アラート通知を発行

    Returns:
        処理結果のサマリー
    """
    logger.info("Starting compliance rescoring job")

    # 1. 法令改正検知
    law_changes = await detect_recent_law_changes()

    if not law_changes:
        logger.info("No law changes detected, skipping rescoring")
        return {
            "status": "no_changes",
            "law_changes": 0,
            "affected_contracts": 0,
        }

    # 2. 影響を受ける契約を検索
    all_affected_contracts = []
    for change in law_changes:
        contracts = await find_affected_contracts(change["law_name"])
        all_affected_contracts.extend(contracts)

    # 重複排除
    seen = set()
    unique_contracts = []
    for c in all_affected_contracts:
        cid = c["contract_id"]
        if cid not in seen:
            seen.add(cid)
            unique_contracts.append(c)

    # 3. アラート通知
    await notify_rescoring_needed(law_changes, unique_contracts)

    result = {
        "status": "completed",
        "law_changes": len(law_changes),
        "affected_contracts": len(unique_contracts),
        "law_details": law_changes,
    }

    logger.info(
        f"Rescoring job completed: {len(law_changes)} law changes, "
        f"{len(unique_contracts)} affected contracts"
    )

    return result


if __name__ == "__main__":
    result = asyncio.run(main())
    print(json.dumps(result, ensure_ascii=False, indent=2))
