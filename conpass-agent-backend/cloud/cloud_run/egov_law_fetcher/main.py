"""
e-Gov法令API連携 Cloud Run サービス
法令テキストを取得してPub/Subに発行する。

Cloud Schedulerから定期的にトリガーされ、対象法令の最新テキストを取得。
変更が検知された場合のみPub/Subに発行し、Embeddingパイプラインで処理される。
"""

import asyncio
import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from google.cloud import pubsub_v1

from change_detector import detect_changes, save_law_hash
from law_parser import parse_law_xml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 取得対象の法令ID一覧
TARGET_LAWS: List[Dict[str, str]] = [
    {"law_id": "109AC0000000055", "name": "民法", "priority": "P0"},
    {"law_id": "032AC0000000048", "name": "商法", "priority": "P0"},
    {"law_id": "024AC0000000100", "name": "建設業法", "priority": "P0"},
    {"law_id": "027AC0000000176", "name": "宅地建物取引業法", "priority": "P0"},
    {"law_id": "022AC0000000049", "name": "労働基準法", "priority": "P1"},
    {"law_id": "415AC0000000057", "name": "個人情報の保護に関する法律", "priority": "P0"},
]

EGOV_BASE_URL = "https://laws.e-gov.go.jp/api/1"

# Pub/Sub設定
PUBSUB_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "")
PUBSUB_TOPIC = os.getenv(
    "LAW_REGULATION_PUBSUB_TOPIC", "conpass-law-regulation"
)


async def fetch_law(law_id: str) -> dict:
    """
    e-Gov APIから法令テキストを取得する。

    Args:
        law_id: e-Gov法令ID

    Returns:
        APIレスポンスのJSONデータ（XML文字列を含む）
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(f"{EGOV_BASE_URL}/lawdata/{law_id}")
        resp.raise_for_status()
        return resp.json()


def parse_articles(law_data: dict, law_name: str, law_id: str) -> List[Dict[str, Any]]:
    """
    法令データを条文単位に分割する。

    e-Gov APIのレスポンスからXML本文を取得し、
    law_parser.parse_law_xml() で編・章・節・条の階層構造を保持したパースを行う。

    Args:
        law_data: e-Gov APIレスポンス
        law_name: 法令名（メタデータ用）
        law_id: 法令ID（メタデータ用）

    Returns:
        条文データのリスト。各要素は以下のフィールドを持つ:
        - law_name, law_id, part, chapter, section,
          article_number, article_title, text
    """
    # e-Gov APIのレスポンスからXML本文を取得
    law_full_text = law_data.get("law_full_text") or law_data.get("LawFullText", "")
    if not law_full_text:
        result = law_data.get("result", {})
        law_full_text = result.get("law_full_text") or result.get("LawFullText", "")

    if not law_full_text:
        logger.warning(f"法令テキストが空です: {law_id} ({law_name})")
        return []

    # law_parser による階層パース（編 > 章 > 節 > 条）
    return parse_law_xml(law_full_text, law_name, law_id)


def publish_to_pubsub(articles: List[Dict[str, Any]], law_name: str) -> None:
    """
    Pub/Subに法令データを発行する。

    source_type: "law_regulation" を設定し、
    generate_embeddingsパイプラインが法令用の処理を適用できるようにする。

    Args:
        articles: 条文データのリスト
        law_name: 法令名（ログ用）
    """
    if not articles:
        logger.info(f"{law_name}: 発行対象の条文なし")
        return

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PUBSUB_PROJECT_ID, PUBSUB_TOPIC)

    # バッチメッセージを構築
    batch_data = {
        "source_type": "law_regulation",
        "law_name": law_name,
        "articles": articles,
        "articles_count": len(articles),
    }

    data_bytes = json.dumps(batch_data, ensure_ascii=False).encode("utf-8")
    message_data = base64.b64encode(data_bytes).decode("utf-8")

    future = publisher.publish(
        topic_path,
        data=data_bytes,
        source_type="law_regulation",
    )
    message_id = future.result()
    logger.info(
        f"{law_name}: {len(articles)}条文をPub/Subに発行 (message_id={message_id})"
    )


async def process_law(law_info: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """
    単一の法令を処理する。

    1. e-Gov APIから法令データを取得
    2. 条文単位に分割
    3. 変更検知（ハッシュ比較）
    4. 変更があればPub/Subに発行

    Args:
        law_info: 法令情報（law_id, name, priority）

    Returns:
        処理結果のdict、またはエラー時None
    """
    law_id = law_info["law_id"]
    law_name = law_info["name"]

    try:
        # 1. e-Gov APIから取得
        law_data = await fetch_law(law_id)
        logger.info(f"{law_name} ({law_id}): APIから取得完了")

        # 2. 条文単位に分割
        articles = parse_articles(law_data, law_name, law_id)
        if not articles:
            logger.warning(f"{law_name}: 条文が抽出できませんでした")
            return {"law_id": law_id, "name": law_name, "status": "no_articles"}

        # 3. 変更検知
        full_text = "\n".join(a["text"] for a in articles)
        has_changes = await detect_changes(law_id, full_text)

        if not has_changes:
            logger.info(f"{law_name}: 変更なし（スキップ）")
            return {"law_id": law_id, "name": law_name, "status": "unchanged"}

        # 4. Pub/Subに発行
        publish_to_pubsub(articles, law_name)

        # 5. ハッシュを保存
        await save_law_hash(law_id, full_text, law_name)

        return {
            "law_id": law_id,
            "name": law_name,
            "status": "updated",
            "articles_count": len(articles),
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"{law_name} ({law_id}): API HTTPエラー {e.response.status_code}")
        return {"law_id": law_id, "name": law_name, "status": "error", "error": str(e)}
    except Exception as e:
        logger.error(f"{law_name} ({law_id}): 処理エラー: {e}", exc_info=True)
        return {"law_id": law_id, "name": law_name, "status": "error", "error": str(e)}


async def main() -> Dict[str, Any]:
    """
    全対象法令を処理するメインエントリポイント。

    Returns:
        処理結果サマリーのdict
    """
    logger.info(f"法令取得開始: {len(TARGET_LAWS)}件の対象法令")

    tasks = [process_law(law) for law in TARGET_LAWS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    summary = {
        "total": len(TARGET_LAWS),
        "updated": 0,
        "unchanged": 0,
        "errors": 0,
        "no_articles": 0,
        "details": [],
    }

    for result in results:
        if isinstance(result, Exception):
            summary["errors"] += 1
            summary["details"].append({"status": "error", "error": str(result)})
        elif result is None:
            summary["errors"] += 1
        else:
            status = result.get("status", "error")
            if status == "updated":
                summary["updated"] += 1
            elif status == "unchanged":
                summary["unchanged"] += 1
            elif status == "no_articles":
                summary["no_articles"] += 1
            else:
                summary["errors"] += 1
            summary["details"].append(result)

    logger.info(
        f"法令取得完了: 更新={summary['updated']}, "
        f"変更なし={summary['unchanged']}, "
        f"エラー={summary['errors']}"
    )

    return summary


# Cloud Run / Cloud Functions エントリポイント
if __name__ == "__main__":
    result = asyncio.run(main())
    print(json.dumps(result, ensure_ascii=False, indent=2))
