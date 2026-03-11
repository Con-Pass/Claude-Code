"""Direct Qdrant HTTP API client for querying with pagination support."""

from typing import Optional, List, Dict, Any
import hashlib
import json
import httpx

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ページネーション: 一度に取得するポイント数
PAGE_SIZE = 10000
# 最大合計ポイント数（安全制限）
MAX_TOTAL_POINTS = 200000


async def scroll_qdrant_with_filter(
    collection_name: str,
    qdrant_filter: Optional[Dict[str, Any]],
    page_size: int = PAGE_SIZE,
) -> List[Dict[str, Any]]:
    """
    Qdrantからフィルタ条件に一致するポイントをページネーションで取得する。

    Args:
        collection_name: コレクション名
        qdrant_filter: Qdrantフィルタ辞書
        page_size: 1ページあたりの取得数

    Returns:
        ポイントのリスト（各要素にid, payloadを含む）
    """
    try:
        url = settings.QDRANT_URL
        api_key = settings.QDRANT_API_KEY

        if not url:
            raise ValueError(
                "Please set QDRANT_URL to your environment variables or config it in the .env file"
            )

        endpoint = f"{url}/collections/{collection_name}/points/scroll"

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["api-key"] = api_key

        all_results = []
        offset = None  # Qdrant scroll APIのカーソル

        async with httpx.AsyncClient(timeout=60.0) as client:
            while True:
                body: Dict[str, Any] = {
                    "limit": page_size,
                    "with_payload": True,
                    "with_vector": False,
                }

                if qdrant_filter:
                    body["filter"] = qdrant_filter

                if offset is not None:
                    body["offset"] = offset

                response = await client.post(endpoint, json=body, headers=headers)
                response.raise_for_status()

                data = response.json()
                result = data.get("result", {})
                points = result.get("points", [])

                for point in points:
                    all_results.append({
                        "id": point.get("id"),
                        "payload": point.get("payload", {}),
                    })

                # 次のページのオフセットを取得
                next_offset = result.get("next_page_offset")

                if next_offset is None or len(all_results) >= MAX_TOTAL_POINTS:
                    break

                offset = next_offset

        logger.info(f"Scroll returned {len(all_results)} results (paginated)")
        return all_results

    except httpx.HTTPStatusError as e:
        logger.error(f"Qdrant HTTP error: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        logger.exception(f"Error scrolling Qdrant: {e}")
        raise
